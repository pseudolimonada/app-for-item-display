import csv
import os
import time
from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from google import genai

class OSRItemPower(BaseModel):
    """Model for an OSR/Cairn-style item power"""
    item_name: str = Field(description="Name of the item")
    osr_power: str = Field(description="Evocative OSR/Cairn-style power description", max_length=500)

class BatchResponse(BaseModel):
    """Model for a batch of OSR item powers"""
    items: List[OSRItemPower] = Field(description="List of items with OSR powers")

def setup_api():
    """Setup the Google Generative AI API client"""
    # Make sure to set GOOGLE_API_KEY in your environment variables
    # export GOOGLE_API_KEY=your-api-key
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable not set")
    
    genai.configure(api_key=api_key)
    return genai.Client()

def process_item_batch(client, items: List[Dict], batch_size: int = 5) -> List[Dict]:
    """Process a batch of items to generate OSR powers"""
    # Prepare batches
    batches = [items[i:i+batch_size] for i in range(0, len(items), batch_size)]
    results = []
    
    for i, batch in enumerate(batches):
        print(f"Processing batch {i+1}/{len(batches)}...")
        
        # Create the prompt for this batch
        batch_prompt = create_batch_prompt(batch)
        
        try:
            # Call Gemini API
            response = client.models.generate_content(
                model="gemini-pro",  # Using pro model for more creative, complex responses
                contents=batch_prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": BatchResponse,
                }
            )
            
            # Extract OSR powers from response
            batch_results: BatchResponse = response.parsed
            
            # Match results with original items
            for j, item in enumerate(batch):
                if j < len(batch_results.items):
                    item_result = batch_results.items[j]
                    item["OSRPower"] = item_result.osr_power
                else:
                    # Fallback if API returns fewer results than expected
                    item["OSRPower"] = "No power generated"
                    
                results.append(item)
                
            print(f"✓ Batch {i+1} processed successfully")
        
        except Exception as e:
            print(f"Error processing batch {i+1}: {e}")
            # Add items with error note
            for item in batch:
                item["OSRPower"] = "Error generating power"
                results.append(item)
        
        # Rate limiting
        if i < len(batches) - 1:  # Don't wait after the last batch
            print("Waiting before next batch...")
            time.sleep(10)
    
    return results

def create_batch_prompt(items: List[Dict]) -> str:
    """Create a prompt for a batch of items"""
    prompt = """Create evocative OSR/Cairn-style magical powers for the following League of Legends items. 
For each item, use its lore and descriptions to craft a power that:
- Focuses on problem-solving and creative use rather than numeric bonuses
- Feels mysterious and somewhat unpredictable 
- Has interesting limitations or drawbacks
- Could create memorable gameplay moments
- Fits the tone and theme of the item

Format your response as a JSON array with fields 'item_name' and 'osr_power' for each item.

Items:
"""

    for item in items:
        prompt += f"\n--- ITEM: {item['Item Name']} ---\n"
        prompt += f"REGION: {item['Region']}\n"
        prompt += f"LORE: {item['Lore']}\n" 
        prompt += f"GAME DESCRIPTION: {item['DescriptionGame']}\n"
        prompt += f"LORE DESCRIPTION: {item['DescriptionLore']}\n\n"

    return prompt

def main():
    """Main function to process items and generate OSR powers"""
    input_csv_file = input("Enter input CSV filename (default: items.csv): ") or "items.csv"
    output_csv_file = input("Enter output CSV filename (default: items_osr.csv): ") or "items_osr.csv"
    
    try:
        # Setup the API client
        client = setup_api()
        
        # Read input CSV
        with open(input_csv_file, "r", encoding="utf-8") as infile:
            reader = csv.DictReader(infile)
            all_items = list(reader)
            
        print(f"Found {len(all_items)} items to process")
        
        # Process items in batches
        processed_items = process_item_batch(client, all_items)
        
        # Write results to output CSV
        # Get all field names from input plus our new field
        fieldnames = list(all_items[0].keys()) + ["OSRPower"]
        
        with open(output_csv_file, "w", encoding="utf-8", newline="") as outfile:
            writer = csv.DictWriter(outfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(processed_items)
        
        print(f"Processing complete. Results saved to '{output_csv_file}'")
            
    except FileNotFoundError:
        print(f"Error: Input file '{input_csv_file}' not found")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
