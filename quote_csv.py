import csv
import sys
import os  # Added missing import


def quote_csv_fields(input_filename, output_filename, delimiter=";"):
    """
    Reads a CSV file and writes a new one with all fields quoted,
    including the header. Uses DictReader/DictWriter for explicit header handling.

    Args:
        input_filename (str): Path to the input CSV file.
        output_filename (str): Path to the output CSV file.
        delimiter (str): The delimiter used in the CSV files.
    """
    try:
        with open(input_filename, "r", encoding="utf-8", newline="") as infile, open(
            output_filename, "w", encoding="utf-8", newline=""
        ) as outfile:

            reader = csv.DictReader(infile, delimiter=delimiter)

            # Check if headers were read successfully
            if not reader.fieldnames:
                print(
                    f"Error: Could not read headers from '{input_filename}'. Is the file empty or format incorrect?"
                )
                return

            # Use QUOTE_ALL to ensure every field is quoted, including the header
            writer = csv.DictWriter(
                outfile, fieldnames=reader.fieldnames, delimiter=delimiter, quoting=csv.QUOTE_ALL
            )

            print(f"Reading from '{input_filename}'...")
            print(f"Writing quoted fields (including header) to '{output_filename}'...")

            # Write the header row, respecting the quoting setting
            writer.writeheader()

            # Write the data rows, respecting the quoting setting
            writer.writerows(reader)

            print("Processing complete.")

    except FileNotFoundError:
        print(f"Error: Input file '{input_filename}' not found.")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    # Default filenames - adjust if needed
    default_input = "items_lore_corrected.csv"
    default_output = "items_lore_quoted.csv"

    # Allow overriding filenames via command-line arguments (optional)
    input_file = sys.argv[1] if len(sys.argv) > 1 else default_input
    output_file = sys.argv[2] if len(sys.argv) > 2 else default_output

    # Construct full paths relative to the script location (optional, adjust as needed)
    script_dir = os.path.dirname(__file__) if "__file__" in locals() else os.getcwd()
    input_path = os.path.join(script_dir, input_file)
    output_path = os.path.join(script_dir, output_file)

    quote_csv_fields(input_path, output_path)
