# Decisions

The tool was born to help my father, who runs a small construction company:
he is "the owner" mentioned below.

## 2026-11-09 — No fixed price list
Items change from one job to the next, and the price depends on the site. The
price comes from the dictation; if it is missing, the system suggests the price
of similar items already used, or leaves the field empty and highlighted.

## 2026-11-09 — One project, two paths
Dictated quotes and the architects' Excel files live in the same project
because they share the archive of items and prices.

## 2026-11-09 — The code does the calculations
The language model understands what was dictated, but amounts, totals and VAT
are calculated in Python, because a model can get the math wrong.

## 2026-11-10 — The quote is a data file, the Word document is only the output
Every quote is saved as a data file (client, address, items, amounts) and the
Word document is regenerated from it. This way the totals are always
calculated by the code, the layout is always the same, and a revision only
requires editing the data. The same files act as the archive of items.

## 2026-11-10 — Many inputs, one path
Voice, photos of handwritten notes and typed text only serve to get a text.
From there on the path is the same: one step turns the text into items and
rewrites it in correct Italian. Adding a new input doesn't touch the rest.

## 2026-11-10 — Start from our own quotes, not from the architects' Excel files
From the analysis of 14 quotes: a single template, items almost always priced
as a lump sum (*a corpo*), and that is where the sum and formatting errors come
from. The architects' and engineers' Excel files have layouts that differ from
one another, and they come later.

## 2026-11-10 — The data holds clean text, and the title without the type
Descriptions are saved already corrected, because the Word document is
regenerated from the data and a typo would be printed again in every version.
The title doesn't contain "Preventivo" or "Consuntivo": the script adds it by
reading the "tipo" field.

## 2026-11-10 — Word template and company data outside the code
The layout lives in a Word file with placeholders such as {{cliente}}; the
script fills them in and adds the table rows. To change fonts or widths, or to
add a logo, you edit the template in Word without touching the code. The
company's data lives in a separate, unpublished file; if it is missing, the
script uses the example data.

## 2026-11-10 — Errors and missing data are two different things
A badly written file (unknown field, a number written as text, amount and
quantity together) stops the script: it is a mistake by whoever produced the
file. Missing data (price, client) is normal when dictating, so the document is
created anyway as a draft (BOZZA), with the list of what to complete. That list
will later be used to ask questions to whoever dictated.

## 2026-11-10 — The math is done with exact decimals
Python's ordinary numbers are approximate, and some quantity-times-price
products came out one cent off. Decimal is used, with half a cent rounded up.

## 2026-11-10 — The script doesn't overwrite and doesn't correct texts
A document that has already been created is never overwritten (max.docx,
max-2.docx...), so a correction made by hand isn't lost. The title is printed
exactly as written in the data, without changing upper and lower case.

## 2026-11-10 — The input is a conversation, not a single dictation
When dictating a quote, people send short messages and correct the data along
the way (25 meters become 28). The tool will keep a draft quote and update it
with each message: a new value replaces the old one, and the list of missing
data becomes the list of questions.

## 2026-11-10 — Descriptions don't add work
The model can write complete descriptions, using the ones already used as
examples, but it doesn't add work that wasn't mentioned: in a quote, everything
described is a commitment to the client. The draft is always shown before the
final document.

## 2026-11-10 — The owner sets the prices, the tool remembers past ones
The owner decides the prices, job by job. The tool doesn't estimate prices: it
suggests the ones already used for similar jobs, taken from the archive; if
there are none, the field stays "da definire" (to be defined).

## 2026-11-10 — The main value is professional writing
Writing the descriptions is the part that takes the most time, so the most
useful thing is turning what the owner says into quote descriptions, in the
style of his documents, using them as examples and without adding work that
wasn't mentioned.

## 2026-11-13 — The tool suggests, it doesn't insert
Revises the decision of 10 November on descriptions. Only what the owner said
or confirmed goes into the document. The tool can, however, suggest items that
recur in his quotes (e.g. the protective covering), prices already used for
similar jobs, and typical details of a kind of work. Every suggestion must be
confirmed before it enters the draft.

## 2026-11-13 — One question at a time, and only if the document needs it
A list of questions often gets only a partial answer, while a single question
almost always gets one. The tool asks one thing at a time. Measurements are
written as they are said ("25 mt"), without guessing whether they are linear,
square or cubic meters.

## 2026-11-13 — Messages can be commands on the draft
Besides adding or correcting a value, a message can ask for a change to the
whole draft ("aumenta di 20%", raise by 20%). The model recognizes the command,
the code does the math.

## 2026-11-14 — A guided form instead of a conversation
Decided with the owner. Prices and advice stay outside the program, which is
for filling in and formatting. The interface is a page with the fields in order
(client, date, site, then for each item the description, lump sum or by
measure, and the price). Every field can be dictated or typed by hand. This
replaces the decisions of 10 and 13 November on the conversation, the questions
and the commands on the draft.

## 2026-11-14 — Who touches what
The client's name stays exactly as it is written. Prices and addresses are
cleaned up by the code (from "593€" to "€ 593,00"), without a model. The
language model only receives the description of the work, and only when asked
to fix the text: names, addresses and prices are never sent to it.

## 2026-11-14 — Three ways to write an item
Lump sum (the total only), by measure with a unit price (the code calculates
the total), by measure with an agreed total (the code derives the unit price).
In the third case, if the division doesn't come out exact to the cent, the unit
price is not printed: what counts is the total decided by the owner, and a
rounded price wouldn't add up for the client.

## 2026-11-15 — Correcting the Italian with Gemini
- First real test: my father made a 16-item quote in about 5 minutes.
- Fixed: the total only updated after leaving the price field. Now it updates while typing.
- New "Sistema il testo" (fix the text) button: it sends only the descriptions to Gemini, never the client, the site or the prices.
- The correction is never automatic: under each changed description the previous text stays visible, with a "Rimetti il mio testo" (restore my text) button.
- The code discards corrections that change a number or the length of the text: better a mistake in Italian than invented work.
- No Google library: the call is made with the standard library, to have fewer dependencies and understand every line.
- The key lives in .env (outside Git). The model is gemini-3.5-flash-lite and can be changed from .env.

## 2026-11-15 — Access password, ahead of putting the page online
- The "Sistema il testo" button works with the real key. On the Mac, Python's certificates were needed ("Install Certificates.command"): that error now has its own message.
- The page only opens with a password (PASSWORD_PAGINA in .env). If no password is set it stays closed: better closed by mistake than open by mistake.
- After logging in you stay logged in for 30 days. After 8 wrong passwords in 10 minutes, the page locks for 10 minutes.
- Online, the company's data will come from a secret setting (IMPRESA_JSON), because data/raw is not on GitHub.
- If the example company's data ends up in the Word document, the page shows a warning.

## 2026-11-15 — Check before publishing
- Checked the whole repository history: no secrets and no real data.
- Tried thousands of requests with odd values: found and fixed six cases where the program crashed (zero quantity with a total price, addresses with staircase and apartment numbers, a site made only of commas, a very long title, invisible characters, huge numbers).
- The link to download the Word document no longer contains the client's name, which ended up in the server logs.
- The page asks the browser not to keep copies and search engines not to list it.

## 2026-11-15 — Second check, with suggestions from another model
- Had Gemini review the code and verified every suggestion with a test: seven applied, five rejected (one claimed that the model in use doesn't exist, which was false).
- Missing data is highlighted in yellow in the Word header too.
- A quantity over a thousand shows a warning: "1.250" with a dot is read as one thousand two hundred and fifty, and the program doesn't try to guess.
- When checking corrections, "2.5" and "2,5" count as the same number, "1.250" and "1,250" don't.
- Lesson learned: test a suggestion before applying it, whoever it comes from.

## 2026-11-15 — Cleanup before publishing
- The address examples now use an invented street in a different town.
- The decisions describe the owner more impersonally; it is still stated that the tool is for my father.
- Removed `strumenti/estrai_chat.py`, left over from an abandoned path.
- README and DECISIONS translated into English. The code, the page and the documents stay in Italian, because the user and the domain are.
- Renamed the repository from preventivi-ai to quote-builder: the AI part is small on purpose, and the old name promised more than the project does.
