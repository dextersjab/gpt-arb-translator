import argparse
import json
import openai
import os
import requests
from tenacity import retry, wait_random_exponential, stop_after_attempt

# Constants
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
API_ENDPOINT = "https://api.openai.com/v1/chat/completions"

openai.api_key = OPENAI_API_KEY

HANDLE_TRANSLATED_TEXT_FUNCTION = [
    {
        "name": "handle_translated_text",
        "description": "Handle the translated text",
        "parameters": {
            "type": "object",
            "properties": {
                "translated_text": {
                    "type": "string",
                    "description": "The translated text",
                },
            },
            "required": ["translated_text"],
        },
    }
]


@retry(wait=wait_random_exponential(min=1, max=40), stop=stop_after_attempt(3))
def request_chat_completion(messages, model, functions=None):
    """
    Function to send chat completion request to OpenAI API.
    Retries the request in case of failure with exponential backoff.
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {openai.api_key}",
    }
    payload = {"model": model, "messages": messages, "functions": functions}

    try:
        response = requests.post(API_ENDPOINT, headers=headers, json=payload)
        response.raise_for_status()
        response_json = response.json()

        # Check for correct format
        function_call = response_json["choices"][0]["message"].get("function_call")
        if function_call is not None and function_call["name"] == "handle_translated_text":
            arguments = json.loads(function_call["arguments"])
            if "translated_text" not in arguments:
                raise ValueError("Incorrect response format.")
        else:
            # When function call is not present, log the issue and return None.
            print(f"Issue with language translation: {response_json['choices'][0]['message']['content']}")
            return None
        print(f"Response: {response_json}")
        return response
    except json.JSONDecodeError:
        print(f"Error decoding function_call arguments. Skipping translation.")
    except (requests.exceptions.HTTPError, ValueError) as err:
        print(f"Error occurred: {err}")
        print(f"Response body: {response.text if response else 'No response'}")
        raise  # Raise the error to trigger retry
    except Exception as e:
        print("Unable to generate ChatCompletion response")
        print(f"Exception: {e}")
        return None



# Command line arguments parsing
parser = argparse.ArgumentParser(
    description='Translate text into multiple languages and update arb files.')
parser.add_argument('--indir', type=str, default='.',
                    help='Input directory containing .arb files (default: current directory)')
parser.add_argument('--outdir', type=str, default=None,
                    help='Output directory for updated .arb files (default: same as indir or '
                         'current directory if indir is not specified)')
parser.add_argument('--entries', type=str, nargs='+', required=True,
                    help='Key-value pairs to add/update in the form key=value')
parser.add_argument('--lang', type=str, default="en", help='Language of input text (default: en)')
parser.add_argument('--out_langs', type=str, nargs='+', default=None,
                    help='Languages to translate into (default: all languages found in arb files)')
parser.add_argument('--model', type=str, default='gpt-3.5-turbo-0613',
                    help='OpenAI GPT model to use for translations (default: gpt-3.5-turbo-0613)')

args = parser.parse_args()


def update_translation_file(file_path, new_entries):
    """
    Function to update a specific translation file with new entries.
    """
    if os.path.isfile(file_path):
        with open(file_path, 'r', encoding='utf-8') as input_file:
            data = json.load(input_file)
    else:
        data = {}

    data.update(new_entries)

    # Sort entries by key in alphabetical order
    sorted_data = {k: data[k] for k in sorted(data)}

    with open(file_path, 'w', encoding='utf-8') as output_file:
        output_file.write(json.dumps(sorted_data, ensure_ascii=False, indent=2))


def main():
    # Set outdir to indir if not specified
    outdir = args.outdir if args.outdir else args.indir
    BATCH_SIZE = 5  # Or any other number that makes sense for your use case
    batch_entries = {}

    # Convert the entries command line argument into a dictionary
    new_entries = {}
    for entry in args.entries:
        if "=" not in entry:
            raise ValueError(f"Invalid format for entry: '{entry}'. Entries should be in the format 'key=value'.")
        key, value = entry.split('=', 1)
        new_entries[key] = {args.lang: value}

    # List of languages to translate into
    if args.out_langs:
        languages = args.out_langs
    else:
        languages = [f.split('_')[1].split('.')[0] for f in os.listdir(args.indir) if
                     os.path.splitext(f)[1] == '.arb']

    # Initialize messages
    messages = [{"role": "system", "content": "You are a helpful assistant."}]

    # Translate each entry into each language
    for lang in languages:
        if lang != args.lang:
            # Read existing keys from the .arb file for this language
            file_path = os.path.join(outdir, f"app_{lang}.arb")
            existing_keys = {}
            if os.path.isfile(file_path):
                with open(file_path, 'r', encoding='utf-8') as input_file:
                    existing_keys = json.load(input_file)
            for i, (key, translations) in enumerate(new_entries.items()):
                # Skip API call if the key already exists
                if key in existing_keys:
                    continue
                input_text = translations[args.lang]
                messages.append({
                    "role": "user",
                    "content": f"""
                    Translate the following {args.lang} text to {lang} (ISO-639-1 code): 
                    "{input_text}".
                    Use the handle_translated_text function to process the translated text.
                    """
                })

                chat_response = request_chat_completion(
                    messages,
                    args.model,
                    functions=HANDLE_TRANSLATED_TEXT_FUNCTION,
                )

                if chat_response is not None and chat_response.status_code == 200:
                    function_call = chat_response.json()["choices"][0]["message"].get("function_call")
                    if function_call is not None and function_call["name"] == "handle_translated_text":
                        translated_text = json.loads(function_call["arguments"])["translated_text"]
                        batch_entries[key] = translated_text

                # Write batched entries to .arb file after every BATCH_SIZE translations
                if (i+1) % BATCH_SIZE == 0:
                    update_translation_file(file_path, batch_entries)
                    batch_entries.clear()

            # Write remaining batched entries to .arb file after translating all entries for the language
            if batch_entries:
                update_translation_file(file_path, batch_entries)
                batch_entries.clear()

    print("Updated .arb files with new entries.")


if __name__ == '__main__':
    main()
