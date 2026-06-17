# Contact import: Google CSV + Monica → Prism

`monica_google_import.py` merges a Google Contacts CSV export and a Monica SQL
dump into one set of people and uploads them to a Prism instance over its API.

- **Google CSV** is treated as the fresher source for phones / emails / addresses.
- **Monica** supplies gender, notes, nickname, and the relationship graph.
- Gender comes from Monica where known, else is inferred from the first name
  ([`gender-guesser`](https://pypi.org/project/gender-guesser/)); ambiguous names
  stay unspecified.
- Family relationships are stored with Prism's generic types (Parent, Sibling, …)
  and rendered with gendered labels (Father/Mother, Brother/Sister) based on each
  contact's gender — so no gendered relationship types are needed.

## Install

```bash
pip install requests gender-guesser
```

## Authenticate

The upload uses a personal API token (Bearer). Prism's Settings UI has no token
section yet, so mint one from a logged-in session:

```bash
# 1) refresh the access cookie from a refresh-token cookie
curl -s -c jar.txt -b 'prism_refresh=<REFRESH_COOKIE>' \
     -X POST https://prism.home.schneider.today/api/auth/refresh
# 2) mint a token (prints the plaintext once)
curl -s -b jar.txt -X POST https://prism.home.schneider.today/api/auth/tokens \
     -H 'content-type: application/json' -d '{"name":"contact-import"}'
```

Revoke it afterwards with `DELETE /api/auth/tokens/{id}`.

## Run

```bash
# dry run (default): writes ./import-preview/merged.json + skipped.json, no writes
python monica_google_import.py --csv contacts.csv --monica monica.sql

# real upload
python monica_google_import.py --csv contacts.csv --monica monica.sql \
    --base-url https://prism.home.schneider.today --token "$PRISM_TOKEN" --apply
```

Idempotent: contacts match by normalized name (create-or-update); a relationship
is skipped if the two people are already linked. New contacts are pushed to
Nextcloud on Prism's next contact sync.
