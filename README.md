# GPT-powered ARB Translator

GPT-ARB-Translator is a Python script that uses OpenAI GPT-3.5-turbo to
translate your arb files. The script is ideal for developers working with
Flutter and looking to localize their applications.

## Installation

1. Clone this repository:

```shell
git clone https://github.com/username/OpenAI-ARB-Translator.git
```

2. Navigate to the cloned directory and install the required Python packages:

```shell
cd OpenAI-ARB-Translator
pip install -r requirements.txt
```

## Usage

1. Set your OpenAI API key as an environment variable:

```shell
export OPENAI_API_KEY='your-key-here'
```

Now you can run the script on the command line. The command-line arguments are:

- `indir`: The directory containing your input .arb files.
- `outdir` (optional): The directory where the translated .arb files will be
  output. Defaults to the input directory if not specified.
- `entries`: Key-value pairs that need to be translated in the format '
  key=value'. You can specify any number of these.
- `lang` (optional): The base language in which the key-value pairs are
  provided, specified as a 2-letter ISO 639-1 code. Defaults to 'en' if not
  specified.
- `out_langs` (optional): Languages to translate into. Defaults to all languages
  found in the arb files in `indir`.

2. Run the script:

```shell
python translate_arbs.py --indir 'your/input/directory' --outdir 'your/output/directory' --entries key1='value1' key2='value2' --lang en
```

## Example

Let's say you want to have arb files that translate the following from English:

```json
{
  "hdtQuote": "The language of friendship is not words but meanings.",
  "noMoat": "We have no moat."
}
```

Here's how you might use the script to translate this quote into multiple
languages:

```shell
python translate_arbs.py --entries "hdtQuote=The language of friendship is not words but meanings." "noMoat=We have no moat." --out_langs en fr es
```

## Notes

- The translated .arb files will retain the structure of the original files,
  with the translated text inserted in place of the original text.
- Make sure to provide valid .arb files in the input directory.
- The script reads the 2-letter language codes from the .arb filenames in the
  input directory. It expects filenames in the format app_<language-code>.arb.
- The script uses the OpenAI GPT-3.5-turbo model for translation.
- If the script encounters an error during translation, it will retry the
  request up to 3 times with an exponential backoff.
- The OpenAI API key is required to use the OpenAI GPT-3.5-turbo model. Keep in
  mind that usage of the OpenAI API may incur costs according to OpenAI's
  pricing.
