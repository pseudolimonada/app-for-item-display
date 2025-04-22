import csv
import os
import time
import json  # Added json import
from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from google import genai

# --- Configuration ---
# Choose the column containing the description you want to correct
# Options might include: 'DescriptionLore', 'DescriptionGame', 'OSRPower', etc.
INPUT_DESCRIPTION_COLUMN = "descriptionlore"
OUTPUT_DESCRIPTION_COLUMN = "Description5e"
DEFAULT_INPUT_CSV = "items.csv"  # Or 'items_osr.csv' if you want to correct OSRPowers
DEFAULT_OUTPUT_CSV = "items_5e.csv"
BATCH_SIZE = 3  # Number of items to process per API call
SLEEP_TIME = 10  # Seconds to wait between batches

# --- Pydantic Models ---


class Item5eDescription(BaseModel):
    """Model for an item description rewritten in D&D 5e style"""

    item_name: str = Field(description="Name of the item")
    corrected_description_5e: str = Field(
        description="Item description rewritten in D&D 5e style language", max_length=1000
    )


class Batch5eResponse(BaseModel):
    """Model for a batch of corrected D&D 5e item descriptions"""

    items: List[Item5eDescription] = Field(
        description="List of items with corrected D&D 5e descriptions"
    )


# --- Functions ---


def setup_api():
    """Setup the Google Generative AI API client"""
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable not set")

    return genai.Client(api_key=api_key)


def process_item_batch(client, items: List[Dict], batch_size: int = BATCH_SIZE) -> List[Dict]:
    """Process a batch of items to generate corrected D&D 5e descriptions"""
    batches = [items[i : i + batch_size] for i in range(0, len(items), batch_size)]
    results = []

    for i, batch in enumerate(batches):
        print(f"Processing batch {i+1}/{len(batches)}...")

        batch_prompt = create_batch_5e_prompt(batch)

        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=batch_prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": Batch5eResponse,
                },
            )

            batch_results = None

            if response.candidates and response.candidates[0].content.parts:
                try:
                    json_text = response.candidates[0].content.parts[0].text
                    if json_text:
                        parsed_data = json.loads(json_text)
                        batch_results = Batch5eResponse.model_validate(parsed_data)
                    else:
                        print(f"Warning: Received empty text content for batch {i+1}.")
                except json.JSONDecodeError as json_err:
                    print(f"Error: Failed to decode JSON response for batch {i+1}: {json_err}")
                    print(f"Received text: {response.candidates[0].content.parts[0].text}")
                except Exception as parse_err:
                    print(
                        f"Error: Failed to parse or validate response for batch {i+1}: {parse_err}"
                    )
                    print(f"Received text: {response.candidates[0].content.parts[0].text}")

            if batch_results:
                results_map = {
                    res.item_name.strip().lower(): res.corrected_description_5e
                    for res in batch_results.items
                }

                for item in batch:
                    item_name_original = item.get("Item Name", "Unknown")
                    item_name_key = item_name_original.strip().lower()

                    if item_name_key in results_map:
                        item[OUTPUT_DESCRIPTION_COLUMN] = results_map[item_name_key]
                    else:
                        print(
                            f"Warning: No corrected description found for '{item_name_original}' (key: '{item_name_key}') in batch {i+1}. Available keys: {list(results_map.keys())}"
                        )
                        item[OUTPUT_DESCRIPTION_COLUMN] = "No description generated"
                    results.append(item)
                print(f"✓ Batch {i+1} processed successfully")
            else:
                print(f"Error: Failed to obtain valid parsed results for batch {i+1}")
                if (
                    response.candidates
                    and response.candidates[0].content.parts
                    and hasattr(response.candidates[0].content.parts[0], "text")
                ):
                    print(f"Raw response text: {response.candidates[0].content.parts[0].text}")
                else:
                    print(
                        f"Raw response content: {response.candidates[0].content if response.candidates else 'No candidates'}"
                    )

                for item in batch:
                    item[OUTPUT_DESCRIPTION_COLUMN] = "Error parsing response"
                    results.append(item)

        except Exception as e:
            print(f"Error processing batch {i+1}: {e}")
            try:
                print(f"Response details on error: {response}")
            except NameError:
                pass
            for item in batch:
                item[OUTPUT_DESCRIPTION_COLUMN] = f"Error: {e}"
                results.append(item)

        if i < len(batches) - 1:
            print(f"Waiting {SLEEP_TIME} seconds before next batch...")
            time.sleep(SLEEP_TIME)

    return results


def create_batch_5e_prompt(items: List[Dict]) -> str:
    """Create a prompt for correcting descriptions to D&D 5e style"""
    prompt = f"""Rewrite the following item's descriptions.
    Guidelines:
    - Your main job is simply to rewrite the mechanics parts of the description to feel a bit more close to 5e.
    - Only substantially change items that feel too bland or weak (all items should feel very rare or stronger).
    - THE DESCRIPTION SHOULD NOT CONTAIN LINE BREAKS.
    - GIVE YOURSELF ENOUGH CREATIVE AGENCY OVER "5e" MECHANICS AS IF YOU WERE THE LEAD DESIGNED OF THE GAME OR A TALENTED HOMEBREW CREATOR.    
    
    The input description is under the '{INPUT_DESCRIPTION_COLUMN}' field.

    Format your response as a JSON object matching the Batch5eResponse schema, containing a list where each item has 'item_name' and 'corrected_description_5e'.


    Items:
    """

    for item in items:
        prompt += f"\n--- ITEM: {item.get('Item Name', 'Unknown')} ---\n"
        prompt += f"REGION: {item.get('Region', 'N/A')}\n"
        prompt += f"LORE: {item.get('Lore', 'N/A')}\n"
        prompt += f"{INPUT_DESCRIPTION_COLUMN}: {item.get(INPUT_DESCRIPTION_COLUMN, 'N/A')}\n\n"

    return prompt


def save_batch(items: List[Dict], fieldnames: List[str], output_file: str, is_first_batch: bool):
    """Save a batch of items to the output CSV file"""
    mode = "w" if is_first_batch else "a"
    with open(output_file, mode, encoding="utf-8", newline="") as outfile:
        writer = csv.DictWriter(
            outfile, fieldnames=fieldnames, extrasaction="ignore", delimiter=";"
        )
        if is_first_batch:
            writer.writeheader()
        writer.writerows(items)


def process_and_save_batches(
    items: List[Dict], fieldnames: List[str], output_file: str, client, batch_size: int = BATCH_SIZE
):
    """Process items in batches and save each batch immediately"""
    batches = [items[i : i + batch_size] for i in range(0, len(items), batch_size)]

    for i, batch in enumerate(batches):
        print(f"\nProcessing batch {i+1}/{len(batches)}...")

        try:
            # Process the batch
            processed_batch = process_item_batch(client, batch, batch_size=len(batch))

            # Save this batch immediately
            is_first_batch = i == 0
            save_batch(processed_batch, fieldnames, output_file, is_first_batch)
            print(f"✓ Batch {i+1} saved successfully")

            # Wait before next batch (except for the last one)
            if i < len(batches) - 1:
                print(f"Waiting {SLEEP_TIME} seconds before next batch...")
                time.sleep(SLEEP_TIME)

        except Exception as e:
            print(f"Error processing/saving batch {i+1}: {e}")
            # Add error message to items and save them anyway
            for item in batch:
                item[OUTPUT_DESCRIPTION_COLUMN] = f"Error: {str(e)}"
            save_batch(batch, fieldnames, output_file, i == 0)
            print(f"Saved batch {i+1} with error messages")


def main():
    """Main function to process items and correct descriptions"""
    input_csv_file = (
        input(f"Enter input CSV filename (default: {DEFAULT_INPUT_CSV}): ") or DEFAULT_INPUT_CSV
    )
    output_csv_file = (
        input(f"Enter output CSV filename (default: {DEFAULT_OUTPUT_CSV}): ") or DEFAULT_OUTPUT_CSV
    )

    try:
        client = setup_api()

        # Read input and validate headers
        with open(input_csv_file, "r", encoding="utf-8-sig") as infile:
            reader = csv.DictReader(infile, delimiter=";")

            detected_headers = reader.fieldnames
            print(f"Detected headers: {detected_headers}")

            cleaned_headers = (
                [header.strip().lower() for header in detected_headers] if detected_headers else []
            )

            input_col_normalized = INPUT_DESCRIPTION_COLUMN.strip().lower()
            if input_col_normalized not in cleaned_headers:
                raise ValueError(
                    f"Error: Column '{INPUT_DESCRIPTION_COLUMN}' (normalized to '{input_col_normalized}') "
                    f"not found in the cleaned headers of '{input_csv_file}'. "
                    f"Detected cleaned headers are: {cleaned_headers}."
                )

            all_items = list(reader)

        if not all_items:
            print("Input file is empty. Exiting.")
            return

        print(f"Found {len(all_items)} items to process from '{input_csv_file}'")

        # Prepare output fieldnames
        fieldnames = (
            detected_headers + [OUTPUT_DESCRIPTION_COLUMN]
            if OUTPUT_DESCRIPTION_COLUMN not in detected_headers
            else detected_headers
        )

        # Create empty output file (will be appended to by process_and_save_batches)
        with open(output_csv_file, "w", encoding="utf-8", newline="") as outfile:
            pass  # Just create/clear the file

        # Process and save items batch by batch
        process_and_save_batches(all_items, fieldnames, output_csv_file, client)

        print(f"\nProcessing complete. All results saved to '{output_csv_file}'")

    except FileNotFoundError:
        print(f"Error: Input file '{input_csv_file}' not found")
    except ValueError as ve:
        print(ve)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    main()
