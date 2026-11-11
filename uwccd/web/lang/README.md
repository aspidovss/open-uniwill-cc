# Interface translations

One JSON file per language, named by its code: `de.json`, `pl.json`, `zh-cn.json`.
How to make one: [docs/TRANSLATING.md](../../../docs/TRANSLATING.md)
(`python3 tools/make_lang_template.py > de.json` makes the blank).

English and Russian are built into the program itself; files here are the other languages,
and missing keys fall back to English, so a partial translation is fine.
