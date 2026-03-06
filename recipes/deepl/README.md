# DeepL Translator

Translate text between German and English using [DeepL](https://www.deepl.com).

## Endpoints

| Endpoint | Description |
|---|---|
| `de-en` | German → English |
| `en-de` | English → German |

## Usage

```
GET /deepl/de-en?q=Wie geht es dir?
GET /deepl/en-de?q=How are you?
```

### Response

Returns the translated text in the `text` field.

## Requirements

- No API key needed — scrapes DeepL's web translator
- No environment variables required

## Notes

- Translation quality matches DeepL's web interface
- Best for short to medium-length text passages
