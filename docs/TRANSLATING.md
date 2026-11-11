# Translating the interface

English and Russian are built in. **Any other language is one JSON file — no code.** A translation covers the
window; the notifications and the tray menu have their own small sections in the same file. What the file does not
translate stays English, key by key, so a partial translation is fine.

## Making a translation

1. Make the template (from the repository):

   ```bash
   python3 tools/make_lang_template.py > de.json
   ```

2. Fill it in:
   - `"name"` — the language's own name, shown in the language list: `"Deutsch"`.
   - `"web"` — the window: English text → translation. Keep the `{0}`, `{1}` placeholders — they are filled with
     values ("Version {0} is available."). Keep the HTML tags where a text has them. Leave a string empty to keep
     English for it.
   - `"service"` — the desktop notifications, `"tray"` — the tray menu (Windows): the keys are short names; the
     English originals are next to them in `service_en` / `tray_en`. Delete those two reference sections when done.

3. Put the file where the service looks (the file name is the language code, [BCP 47](https://en.wikipedia.org/wiki/IETF_language_tag), lower case):

   | Where | Path | When |
   |---|---|---|
   | installed copy | Linux `/var/lib/uwcc/langs/de.json` · Windows `%ProgramData%\UWCC\data\langs\de.json` | trying it on your laptop |
   | repository | `uwccd/web/lang/de.json` | sending it to the project |

4. Reload the window (F5). The new language appears in the language switch (bottom of the side bar) and in
   `GET /api/langs`; mistakes are written to the service log.

The user agreement is shown in English for other languages (translations of a legal text need review), and the
console tool `uwccctl` and the Linux agent notifications stay English/Russian for now.

## Sending it to the project

Open a pull request that adds `uwccd/web/lang/<code>.json` — nothing else is needed. Please state in the pull
request that the translation is your own work (it is published under the repository's MIT license), and add
yourself to [CONTRIBUTORS.md](../CONTRIBUTORS.md).

When interface texts change in a release, missing keys simply stay English: a translation never breaks.
`tools/make_lang_template.py` plus a diff shows what is new.
