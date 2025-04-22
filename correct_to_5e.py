import csv
import os
import time
from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from google import genai

# --- Configuration ---
# Choose the column containing the description you want to correct
# Options might include: 'DescriptionLore', 'DescriptionGame', 'OSRPower', etc.
INPUT_DESCRIPTION_COLUMN = 'DescriptionLore' 
OUTPUT_DESCRIPTION_COLUMN = 'Description5e'
DEFAULT_INPUT_CSV = 'items.csv' # Or 'items_osr.csv' if you want to correct OSRPowers
DEFAULT_OUTPUT_CSV = 'items_5e.csv'
BATCH_SIZE = 5 # Number of items to process per API call
SLEEP_TIME = 10 # Seconds to wait between batches

# --- Pydantic Models ---

class Item5eDescription(BaseModel):
    """Model for an item description rewritten in D&D 5e style"""
    item_name: str = Field(description="Name of the item")
    corrected_description_5e: str = Field(description="Item description rewritten in D&D 5e style language", max_length=1000)

class Batch5eResponse(BaseModel):
    """Model for a batch of corrected D&D 5e item descriptions"""
    items: List[Item5eDescription] = Field(description="List of items with corrected D&D 5e descriptions")

# --- Functions ---

def setup_api():
    """Setup the Google Generative AI API client"""
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable not set")
    
    genai.configure(api_key=api_key)
    return genai.Client()

def process_item_batch(client, items: List[Dict], batch_size: int = BATCH_SIZE) -> List[Dict]:
    """Process a batch of items to generate corrected D&D 5e descriptions"""
    batches = [items[i:i+batch_size] for i in range(0, len(items), batch_size)]
    results = []
    
    for i, batch in enumerate(batches):
        print(f"Processing batch {i+1}/{len(batches)}...")
        
        batch_prompt = create_batch_5e_prompt(batch)
        
        try:
            response = client.models.generate_content(
                model="gemini-pro", 
                contents=batch_prompt,
                generation_config={ # Added generation config for potentially better control
                    "temperature": 0.6, 
                },
                safety_settings={ # Optional: Adjust safety settings if needed
                     'HATE': 'BLOCK_NONE',
                     'HARASSMENT': 'BLOCK_NONE',
                     'SEXUAL' : 'BLOCK_NONE',
                     'DANGEROUS' : 'BLOCK_NONE'
                },
                request_options={ # Added timeout
                    "timeout": 120, # seconds
                },
                # Updated schema for 5e correction
                tool_config={
                    "function_calling_config": {
                        "mode": "ANY",
                        "allowed_function_names": ["Batch5eResponse"] 
                    }
                },
                 tools=[Batch5eResponse] # Pass the Pydantic model directly
            )

            # Extract corrected descriptions
            # Accessing the function call response might differ slightly depending on API version
            # This assumes the API directly returns the parsed Pydantic object or similar structure
            if response.candidates and response.candidates[0].content.parts:
                 # Assuming the function call/structured response is the first part
                 function_call_part = response.candidates[0].content.parts[0]
                 # Adapt based on actual response structure, might be response.candidates[0].function_calls[0]
                 # Or if using response_schema, it might be response.parsed
                 
                 # Placeholder: Adapt this extraction logic based on actual API response structure
                 # For demonstration, assuming a direct parse or accessible structure:
                 try:
                     # Attempt direct parsing if available
                     batch_results: Batch5eResponse = response.candidates[0].content.parts[0].function_call # Adjust path as needed
                 except AttributeError:
                      # Fallback or alternative extraction if the above path is wrong
                      print(f"Warning: Could not directly parse batch {i+1}. Check API response structure.")
                      # Manual parsing might be needed here based on print(response)
                      batch_results = None # Set to None or handle error

                 if batch_results:
                    # Match results with original items
                    results_map = {res.item_name: res.corrected_description_5e for res in batch_results.items}
                    
                    for item in batch:
                        item_name = item.get('Item Name', 'Unknown')
                        if item_name in results_map:
                            item[OUTPUT_DESCRIPTION_COLUMN] = results_map[item_name]
                        else:
                            print(f"Warning: No corrected description found for '{item_name}' in batch {i+1}")
                            item[OUTPUT_DESCRIPTION_COLUMN] = "No description generated"
                        results.append(item)
                    print(f"✓ Batch {i+1} processed successfully")
                 else:
                      # Handle case where batch_results could not be parsed
                      print(f"Error: Failed to parse results for batch {i+1}")
                      for item in batch:
                          item[OUTPUT_DESCRIPTION_COLUMN] = "Error parsing response"
                          results.append(item)

            else:
                 print(f"Error: No valid response content received for batch {i+1}")
                 for item in batch:
                     item[OUTPUT_DESCRIPTION_COLUMN] = "Error receiving response"
                     results.append(item)

        except Exception as e:
            print(f"Error processing batch {i+1}: {e}")
            for item in batch:
                item[OUTPUT_DESCRIPTION_COLUMN] = f"Error: {e}"
                results.append(item)
        
        if i < len(batches) - 1:
            print(f"Waiting {SLEEP_TIME} seconds before next batch...")
            time.sleep(SLEEP_TIME)
    
    return results

def create_batch_5e_prompt(items: List[Dict]) -> str:
    """Create a prompt for correcting descriptions to D&D 5e style"""
    prompt = f"""Rewrite the following item descriptions using standard Dungeons & Dragons 5th Edition (D&D 5e) terminology and phrasing. 
Focus on clarity, mechanics commonly found in 5e (like actions, bonus actions, reactions, saving throws, conditions, attunement), and official WotC style. Use the item's name, region, and lore for context. The input description is under the '{INPUT_DESCRIPTION_COLUMN}' field.

Format your response as a JSON object matching the Batch5eResponse schema, containing a list where each item has 'item_name' and 'corrected_description_5e'.

Items:
"""

    for item in items:
        prompt += f"\n--- ITEM: {item.get('Item Name', 'Unknown')} ---\n"
        prompt += f"REGION: {item.get('Region', 'N/A')}\n"
        prompt += f"LORE: {item.get('Lore', 'N/A')}\n" 
        # Include the specific description column to be corrected
        prompt += f"{INPUT_DESCRIPTION_COLUMN}: {item.get(INPUT_DESCRIPTION_COLUMN, 'N/A')}\n\n" 

    return prompt

def main():
    """Main function to process items and correct descriptions"""
    input_csv_file = input(f"Enter input CSV filename (default: {DEFAULT_INPUT_CSV}): ") or DEFAULT_INPUT_CSV
    output_csv_file = input(f"Enter output CSV filename (default: {DEFAULT_OUTPUT_CSV}): ") or DEFAULT_OUTPUT_CSV
    
    try:
        client = setup_api()
        
        with open(input_csv_file, "r", encoding="utf-8") as infile:
            reader = csv.DictReader(infile)
            # Check if the input description column exists
            if INPUT_DESCRIPTION_COLUMN not in reader.fieldnames:
                 raise ValueError(f"Error: Column '{INPUT_DESCRIPTION_COLUMN}' not found in '{input_csv_file}'. Please check INPUT_DESCRIPTION_COLUMN setting.")
            all_items = list(reader)
            original_fieldnames = reader.fieldnames
            
        if not all_items:
            print("Input file is empty. Exiting.")
            return

        print(f"Found {len(all_items)} items to process from '{input_csv_file}'")
        
        processed_items = process_item_batch(client, all_items)
        
        # Ensure the output column is added if it wasn't already there
        fieldnames = original_fieldnames + [OUTPUT_DESCRIPTION_COLUMN] if OUTPUT_DESCRIPTION_COLUMN not in original_fieldnames else original_fieldnames
        
        with open(output_csv_file, "w", encoding="utf-8", newline="") as outfile:
            writer = csv.DictWriter(outfile, fieldnames=fieldnames, extrasaction='ignore') # Ignore extra fields if any
            writer.writeheader()
            writer.writerows(processed_items)
        
        print(f"Processing complete. Results saved to '{output_csv_file}'")
            
    except FileNotFoundError:
        print(f"Error: Input file '{input_csv_file}' not found")
    except ValueError as ve:
        print(ve)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
