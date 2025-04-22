import csv
import os
import time
import json
from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from google import genai
from google.genai.types import (
    GenerateContentResponse,
    GenerationConfig,
    GenerateContentConfig,
    Tool,
    GoogleSearch,
    Content,
    Part,
)

# --- Configuration ---
# Columns to use for context and correction
INPUT_LORE_COLUMN = "Lore"
INPUT_REGION_COLUMN = "Region"
INPUT_NAME_COLUMN = "Item Name"  # Added for context
INPUT_DESCRIPTION_COLUMN = "DescriptionLore"  # Added for context

# Columns required in the input file to ensure they can be carried over to the output
REQUIRED_INPUT_COLUMNS_FOR_OUTPUT = ["Item Name", "Region", "Lore", "DescriptionLore", "ImageURL"]

DEFAULT_INPUT_CSV = "items.csv"
DEFAULT_OUTPUT_CSV = "items_lore_corrected.csv"
BATCH_SIZE = 5  # Adjust as needed, lore correction might need more context per item
SLEEP_TIME = 10  # Seconds to wait between batches
MODEL_ID = "gemini-2.0-flash"
GOOGLE_SEARCH_TOOL = Tool(google_search=GoogleSearch())
# --- Pydantic Models ---


class ItemLoreCorrection(BaseModel):
    """Model for an item's corrected lore and region"""

    item_name: str = Field(description="Name of the item (must match input)")
    corrected_region: str = Field(
        description="The corrected region assignment based on lore context (e.g., Valoran, Piltover, Zaun, Ionia, etc.)"
    )
    corrected_lore: str = Field(
        description="Item lore rewritten for consistency and accuracy within the Runeterra universe",
        max_length=1500,
    )


class BatchLoreResponse(BaseModel):
    """Model for a batch of corrected item lore and regions"""

    items: List[ItemLoreCorrection] = Field(
        description="List of items with corrected lore and regions"
    )


# --- Functions ---


def setup_api():
    """Setup the Google Generative AI API client"""
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable not set")
    try:
        return genai.Client(api_key=api_key)
    except ImportError:
        raise ImportError(
            "google.generativeai library not found. Please install it (`pip install google-generativeai`)."
        )
    except Exception as e:
        raise RuntimeError(f"Failed to configure Google Generative AI: {e}")


# --- New Helper Functions for Prompts ---


def create_info_gathering_prompt(items: List[Dict]) -> str:
    """Create a prompt to gather information and context about items."""
    prompt = f"""For the following Runeterra items, gather relevant context regarding their likely origin, lore connections, and potential region inconsistencies. Focus on details that would help correct their 'Region' and 'Lore'. Use search if necessary to find the most up-to-date or accurate information. Provide the gathered context concisely for each item.

Input Items:
"""
    for item in items:
        prompt += f"\n--- ITEM ---\n"
        prompt += f"Item Name: {item.get(INPUT_NAME_COLUMN, 'Unknown')}\n"
        prompt += f"Current Region: {item.get(INPUT_REGION_COLUMN, 'N/A')}\n"
        prompt += f"Current Lore: {item.get(INPUT_LORE_COLUMN, 'N/A')}\n"
        prompt += f"Description ({INPUT_DESCRIPTION_COLUMN}): {item.get(INPUT_DESCRIPTION_COLUMN, 'N/A')}\n"
        prompt += "---\n"
    prompt += "\nConsolidated Context:"
    return prompt


def create_correction_prompt(items: List[Dict], gathered_context: str) -> str:
    """Create a prompt to correct lore/region using gathered context, requesting JSON output."""
    prompt = f"""Based on the original item data and the following gathered context, correct the 'Region' and rewrite the 'Lore' for each item. Ensure the rewritten lore is accurate, consistent with Runeterra, and engaging.

**Gathered Context:**
{gathered_context}

**Guidelines:**
1.  **Region Correction:** Assign the most appropriate region (e.g., Piltover, Zaun, Valoran, Ionia) based on all available information.
2.  **Lore Rewriting:** Rewrite the '{INPUT_LORE_COLUMN}' to be concise, evocative, and consistent with the corrected region and item function. Max length ~1500 characters.
3.  **Output Format:** Format your response strictly as a JSON object matching the BatchLoreResponse schema. The JSON must contain a list named 'items', each with 'item_name' (exact match), 'corrected_region', and 'corrected_lore'. Do not include ```json markdown fences.
4.  **Consistency:** Ensure 'item_name' in the output matches the input 'Item Name' exactly.

**Input Items (for reference):**
"""
    for item in items:
        prompt += f"\n--- ITEM ---\n"
        prompt += f"Item Name: {item.get(INPUT_NAME_COLUMN, 'Unknown')}\n"
        prompt += f"Current Region: {item.get(INPUT_REGION_COLUMN, 'N/A')}\n"
        prompt += f"Current Lore: {item.get(INPUT_LORE_COLUMN, 'N/A')}\n"
        prompt += f"Description ({INPUT_DESCRIPTION_COLUMN}): {item.get(INPUT_DESCRIPTION_COLUMN, 'N/A')}\n"
        prompt += "---\n"

    prompt += "\nJSON Output:"
    return prompt


# --- Modified process_item_batch Function ---


def process_item_batch(
    client: genai.Client, items: List[Dict], batch_size: int = BATCH_SIZE
) -> List[Dict]:
    """Process a batch using a two-step query: 1. Gather info with search, 2. Correct with JSON output."""
    print(f"Processing batch of {len(items)} items (2-step query)...")
    results = []
    gathered_context = "No context gathered."  # Default context

    # --- Step 1: Information Gathering Query ---
    print("Step 1: Gathering context...")
    info_prompt = create_info_gathering_prompt(items)
    try:
        info_response = client.models.generate_content(
            model=MODEL_ID,
            contents=info_prompt,
            config=GenerateContentConfig(tools=[GOOGLE_SEARCH_TOOL]),
        )
        if info_response.candidates and info_response.candidates[0].content.parts:
            gathered_context = info_response.candidates[0].content.parts[0].text
            print("✓ Context gathered successfully.")
        else:
            print("Warning: No context could be gathered from the first query.")
            if info_response.candidates:
                for i, candidate in enumerate(info_response.candidates):
                    if candidate.finish_reason:
                        print(f"  Candidate {i} Finish reason: {candidate.finish_reason}")
                    if candidate.safety_ratings:
                        print(f"  Candidate {i} Safety ratings: {candidate.safety_ratings}")

    except Exception as e:
        print(f"Error during Step 1 (Information Gathering): {e}")
        gathered_context = (
            f"Error gathering context: {e}"  # Store error in context for step 2 prompt
        )

    # --- Step 2: Correction Query ---
    print("Step 2: Generating corrections...")
    correction_prompt = create_correction_prompt(items, gathered_context)
    batch_results_model = None

    try:
        correction_response = client.models.generate_content(
            model=MODEL_ID,
            contents=correction_prompt,
            config=GenerateContentConfig(
                response_mime_type="application/json", response_schema=BatchLoreResponse
            ),
        )

        if correction_response.candidates and correction_response.candidates[0].content.parts:
            try:
                json_text = correction_response.candidates[0].content.parts[0].text
                if json_text:
                    if json_text.strip().startswith("```json"):
                        json_text = json_text.strip()[7:-3].strip()
                    elif json_text.strip().startswith("```"):
                        json_text = json_text.strip()[3:-3].strip()

                    parsed_data = json.loads(json_text)
                    batch_results_model = BatchLoreResponse.model_validate(parsed_data)
                else:
                    print("Warning: Received empty text content for correction batch.")

            except json.JSONDecodeError as json_err:
                print(f"Error: Failed to decode JSON response for correction batch: {json_err}")
                print(
                    f"Received text: {correction_response.candidates[0].content.parts[0].text if correction_response.candidates and correction_response.candidates[0].content.parts else 'No text part'}"
                )
            except Exception as parse_err:
                print(
                    f"Error: Failed to parse or validate response for correction batch: {parse_err}"
                )
                try:
                    print(
                        f"Raw correction response content: {correction_response.candidates[0].content.to_dict() if correction_response.candidates else 'No candidates'}"
                    )
                except Exception as print_err:
                    print(f"Could not print raw correction response content: {print_err}")
        else:
            print("Error: No response content received for correction batch.")
            if correction_response.candidates:
                for i, candidate in enumerate(correction_response.candidates):
                    if candidate.finish_reason:
                        print(f"  Candidate {i} Finish reason: {candidate.finish_reason}")
                    if candidate.safety_ratings:
                        print(f"  Candidate {i} Safety ratings: {candidate.safety_ratings}")

        if batch_results_model and batch_results_model.items:
            results_map = {}
            for res in batch_results_model.items:
                if res.item_name:
                    results_map[res.item_name.strip().lower()] = {
                        "region": res.corrected_region,
                        "lore": res.corrected_lore,
                    }

            for item in items:
                item_name_original = item.get(INPUT_NAME_COLUMN, "Unknown")
                item_name_key = item_name_original.strip().lower()

                if item_name_key in results_map:
                    item[INPUT_REGION_COLUMN] = results_map[item_name_key]["region"]
                    item[INPUT_LORE_COLUMN] = results_map[item_name_key]["lore"]
                else:
                    print(
                        f"Warning: No corrected data found for '{item_name_original}' (key: '{item_name_key}'). Available keys: {list(results_map.keys())}"
                    )
                    item[INPUT_REGION_COLUMN] = f"Error: No data returned for item"
                    item[INPUT_LORE_COLUMN] = "Error: No data returned for item"
                results.append(item)
            print(f"✓ Batch processed successfully")

        else:
            print(
                f"Error: Failed to obtain valid parsed results for the correction batch or batch_results_model.items is empty."
            )
            for item in items:
                item[INPUT_REGION_COLUMN] = "Error: Failed parsing correction response"
                item[INPUT_LORE_COLUMN] = "Error: Failed parsing correction response"
                results.append(item)

    except Exception as e:
        print(f"Error processing Step 2 (Correction): {e}")
        try:
            print(f"Correction Response details on error: {correction_response}")
        except NameError:
            pass
        for item in items:
            item[INPUT_REGION_COLUMN] = f"Error during correction: {str(e)}"
            item[INPUT_LORE_COLUMN] = f"Error during correction: {str(e)}"
            results.append(item)

    return results


def save_batch(items: List[Dict], fieldnames: List[str], output_file: str, is_first_batch: bool):
    """Save a batch of items to the output CSV file, quoting all fields."""
    mode = "w" if is_first_batch else "a"
    try:
        with open(output_file, mode, encoding="utf-8", newline="") as outfile:
            # Add quoting=csv.QUOTE_ALL to ensure all fields are quoted
            writer = csv.DictWriter(
                outfile,
                fieldnames=fieldnames,
                extrasaction="ignore",
                delimiter=";",
                quoting=csv.QUOTE_ALL,  # Ensure all fields are quoted
            )
            if is_first_batch:
                writer.writeheader()  # writeheader() will also respect QUOTE_ALL
            writer.writerows(items)
    except IOError as e:
        print(f"Error writing to output file {output_file}: {e}")
        raise


def process_and_save_batches(
    items: List[Dict],
    fieldnames: List[str],
    output_file: str,
    client: genai.Client,
    batch_size: int = BATCH_SIZE,
):
    """Process items in batches and save each batch immediately"""
    total_items = len(items)
    num_batches = (total_items + batch_size - 1) // batch_size

    for i in range(num_batches):
        start_index = i * batch_size
        end_index = start_index + batch_size
        batch = items[start_index:end_index]

        print(f"\n--- Processing Batch {i+1}/{num_batches} ({len(batch)} items) ---")

        try:
            processed_batch = process_item_batch(client, batch, batch_size)

            is_first = i == 0
            save_batch(processed_batch, fieldnames, output_file, is_first)
            print(f"✓ Batch {i+1} saved successfully to '{output_file}'")

        except Exception as e:
            print(f"!! Critical Error processing/saving batch {i+1}: {e}")
            error_batch = []
            for item in batch:
                item[INPUT_REGION_COLUMN] = f"Error during batch processing: {str(e)}"
                item[INPUT_LORE_COLUMN] = f"Error during batch processing: {str(e)}"
                error_batch.append(item)
            try:
                is_first = i == 0
                save_batch(error_batch, fieldnames, output_file, is_first)
                print(f"Saved batch {i+1} with critical error messages")
            except Exception as save_e:
                print(f"!!! Failed to save batch {i+1} even with error messages: {save_e}")

        if i < num_batches - 1:
            print(f"Waiting {SLEEP_TIME} seconds before next batch...")
            time.sleep(SLEEP_TIME)


def main():
    """Main function to process items and correct lore/regions"""
    input_csv_file = (
        input(f"Enter input CSV filename (default: {DEFAULT_INPUT_CSV}): ") or DEFAULT_INPUT_CSV
    )
    output_csv_file = (
        input(f"Enter output CSV filename (default: {DEFAULT_OUTPUT_CSV}): ") or DEFAULT_OUTPUT_CSV
    )

    try:
        client = setup_api()

        output_fieldnames = ["Item Name", "Region", "Lore", "DescriptionLore", "ImageURL"]

        client = setup_api()

        output_fieldnames = ["Item Name", "Region", "Lore", "DescriptionLore", "ImageURL"]

        all_items = []
        detected_headers = []
        with open(input_csv_file, "r", encoding="utf-8-sig") as infile:
            reader = csv.DictReader(infile, delimiter=";")

            detected_headers = reader.fieldnames
            if not detected_headers:
                print(f"Warning: No headers found in '{input_csv_file}'.")
                return

            print(f"Detected headers: {detected_headers}")

            header_map = {header.strip().lower(): header for header in detected_headers}

            required_cols_for_processing = [
                INPUT_LORE_COLUMN,
                INPUT_REGION_COLUMN,
                INPUT_NAME_COLUMN,
                INPUT_DESCRIPTION_COLUMN,
            ]
            required_cols_for_output_check = REQUIRED_INPUT_COLUMNS_FOR_OUTPUT

            missing_cols = []
            all_required_cols = set(required_cols_for_processing + required_cols_for_output_check)

            for col in all_required_cols:
                col_normalized = col.strip().lower()
                if col_normalized not in header_map:
                    missing_cols.append(col)

            if missing_cols:
                missing_cols_original_case = []
                detected_lower_to_original = {h.strip().lower(): h for h in detected_headers}
                for col in missing_cols:
                    col_lower = col.strip().lower()
                    if col_lower in detected_lower_to_original:
                        missing_cols_original_case.append(detected_lower_to_original[col_lower])
                    else:
                        missing_cols_original_case.append(col)

                raise ValueError(
                    f"Error: Required columns {list(set(missing_cols_original_case))} not found in '{input_csv_file}'. "
                    f"These columns are needed either for processing or for the final output header. "
                    f"Detected headers are: {detected_headers}."
                )

            all_items = list(reader)

        if not all_items:
            print("Input file is empty. Exiting.")
            return

        print(f"Found {len(all_items)} items to process from '{input_csv_file}'")

        try:
            with open(output_csv_file, "w", encoding="utf-8", newline="") as outfile:
                pass
        except IOError as e:
            print(f"Error initializing output file {output_csv_file}: {e}")
            return

        process_and_save_batches(all_items, output_fieldnames, output_csv_file, client, BATCH_SIZE)

        print(f"\nProcessing complete. Results saved to '{output_csv_file}'")

    except FileNotFoundError:
        print(f"Error: Input file '{input_csv_file}' not found")
    except ValueError as ve:
        print(f"Configuration Error: {ve}")
    except ImportError as ie:
        print(f"Import Error: {ie}. Make sure required libraries are installed.")
    except RuntimeError as re:
        print(f"Runtime Error: {re}")
    except Exception as e:
        import traceback

        print(f"An unexpected error occurred: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
