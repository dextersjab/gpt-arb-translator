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

        function_call = response_json["choices"][0]["message"].get("function_call")
        if function_call is not None and function_call["name"] == "handle_translated_text":
            arguments = json.loads(function_call["arguments"])
            if "translated_text" not in arguments:
                raise ValueError("Incorrect response format.")
        else:
            print(f"Issue with language translation: {response_json['choices'][0]['message']['content']}")
            return None
        print(f"Response: {response_json}")
        return response
    except json.JSONDecodeError:
        print(f"Error decoding function_call arguments. Skipping translation.")
    except (requests.exceptions.HTTPError, ValueError) as err:
        print(f"Error occurred: {err}")
        print(f"Response body: {response.text if response else 'No response'}")
        raise
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
    print(f"{file_path=}")
    print(f"{new_entries=}")
    if os.path.isfile(file_path):
        with open(file_path, 'r', encoding='utf-8') as input_file:
            data = json.load(input_file)
    else:
        data = {}

    data.update(new_entries)
    sorted_data = {k: data[k] for k in sorted(data)}

    with open(file_path, 'w', encoding='utf-8') as output_file:
        output_file.write(json.dumps(sorted_data, ensure_ascii=False, indent=2))

def main():
    # Set outdir to indir if not specified
    outdir = args.outdir if args.outdir else args.indir
    BATCH_SIZE = 5  # Or any other number that makes sense for your use case
    batch_entries = {}

    # Load entries from the base language file
    base_lang_file_path = os.path.join(args.indir, f"app_{args.lang}.arb")
    if not os.path.isfile(base_lang_file_path):
        raise ValueError(f"Base language file not found: {base_lang_file_path}")

    with open(base_lang_file_path, 'r', encoding='utf-8') as input_file:
        base_lang_entries = json.load(input_file)

    if args.out_langs:
        languages = args.out_langs
    else:
        languages = [f.split('_')[1].split('.')[0] for f in os.listdir(args.indir) if
                     os.path.splitext(f)[1] == '.arb']

    messages = [{"role": "system", "content": "You are a helpful assistant."}]

    for lang in languages:
        if lang != args.lang:
            file_path = os.path.join(outdir, f"app_{lang}.arb")
            existing_keys = {}
            if os.path.isfile(file_path):
                with open(file_path, 'r', encoding='utf-8') as input_file:
                    existing_keys = json.load(input_file)

            for i, (key, value) in enumerate(base_lang_entries.items()):
                if key in existing_keys:
                    continue
                messages.append({
                    "role": "user",
                    "content": f"""
                    Translate the following {args.lang} text to {lang} (ISO-639-1 code): 
                    "{value}".
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

                if (i+1) % BATCH_SIZE == 0:
                    update_translation_file(file_path, batch_entries)
                    batch_entries.clear()

            if batch_entries:
                update_translation_file(file_path, batch_entries)
                batch_entries.clear()

    print("Updated .arb files with new entries.")

if __name__ == '__main__':
    main()
