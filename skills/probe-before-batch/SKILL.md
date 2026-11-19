---
name: probe-before-batch
description: |
  Before launching any multi-item scrape/search/API batch, run ONE item
  end-to-end first and confirm the OUTPUT is actually parseable (not just
  that the source responds). Sources differ wildly — one probe saves a
  failed 90-item run.
allowed-tools: |
  Bash, mcp__playwright
---

# Probe Before Batch

<purpose>
A batch over N items inherits the failure mode of item #1 — N times. If the
source blocks bots, rate-limits, or returns data you can't parse, you don't
find out until you've burned the whole run (and possibly tripped rate limits
that take an IP rotation to clear). One end-to-end probe of a single item,
checking the PARSED result and not just the HTTP response, catches all of it.
</purpose>

## When To Activate

- About to loop a scraper / search / API call over more than ~5 items
- About to run a price audit, catalog pull, or research batch
- Switching the batch to a NEW source, site, query shape, or product type
  (the previous probe does NOT cover a new source)

## Instructions

1. **Probe one representative item end-to-end** through the exact tool/query
   the batch will use — not a simplified version.
2. **Inspect the PARSED output, not just "did it respond."** Ask:
   - Did results come back? (count > 0)
   - Is the field I actually need present and extractable? (e.g. a *price*,
     not just a page that exists)
3. **DIFFERENTIAL PROBE — run TWO different inputs per source and confirm the
   outputs DIFFER.** A parsed value is NOT proof the search filtered on your
   input. No-results pages, featured/cross-sell blocks, and cached homepages all
   return a plausible-looking price. If query A and query B return the *same*
   price (or the same grid of prices), the search isn't matching — the value is
   garbage no matter how clean it looks. Also reject grid dumps: if one query
   returns 40+ prices, you're scraping the whole results page, not the item.
3a. **VERIFY PROVENANCE — capture WHERE the value came from, not just the value.**
   A differential probe still lies if your extractor reads page chrome. Have the
   probe return the source element / product name alongside the price. Two failure
   shapes this catches: (a) the value was scraped from the *search-echo* —
   `<title>Search results for 'ABC-123-456'</title>` contains your query, so a
   naive "find my term, grab the nearest $" climbs to a banner price identical on
   every search; (b) the matched product NAME doesn't relate to your input (site
   returned generic/featured items). Rule: extract from a real PRODUCT card (a
   product link, excluding nav/title/script), and trust the price only if the
   card's name corresponds to the input. When a result looks uniform or wrong,
   DUMP what element matched before concluding "the source lacks the data" —
   usually it's your extractor, not the site.
4. **If switching sources mid-task, re-probe.** One retailer's search snippets
   carry prices; a niche parts site returns results with NO snippet price; a third
   blocks headless browsers outright. Each source is its own probe.
5. **Only after a clean parsed result, launch the batch.** Add pacing and retry if
   the source is rate-limit-prone (shared metasearch instances suspend engines fast).

## NEVER

- Launch a batch because the source "should work" or worked for a different
  product type / different site
- Treat "HTTP 200 / results returned" as success — verify the needed field
  is actually extractable
- Trust a single parsed value — a fixed/featured/no-results price looks
  identical to a real one. Probe a SECOND distinct input and require it to differ.
- Accept a grid dump (dozens of prices from one query) as "the item's price"
- Run two scrape batches against the same aggregator concurrently (doubles
  the rate and trips suspension)

## ALWAYS

- Probe one item, read the parsed value, THEN loop
- Re-probe when the source, query shape, or product line changes
- Kill a running batch the moment you see `sources=0` / blank fields repeating
  — don't let it grind out a file of zeros

## The Failures That Spawned This Skill

1. A retail price audit probed one big retailer first (caught "Access Denied" and
   avoided a 90-part dead run), but a second batch for a different product line
   launched WITHOUT a probe. Those niche sites return results with no price in the
   snippet, so the batch produced 31 rows of `no retail price found`. A 10-second
   probe would have shown `prices=[]`. Two concurrent metasearch batches also
   tripped engine CAPTCHAs and needed an IP change and a container restart.
2. The next round probed each of 6 retailers with ONE part, saw prices, and
   launched 28 parts. The first record exposed it: one site returned the IDENTICAL
   price pair for two different parts (a featured fallback, not the part), and
   another dumped 45 grid prices. The estimate came out at $1400 for a $169 part.
   A differential probe (two parts per retailer, prices must differ) would have
   flagged both before the batch ran.
3. The round after that ran a correct differential probe, saw identical prices
   across two parts on two sites, and concluded "these sites don't filter." The
   user asked for a sanity check. A provenance dump proved the extractor matched
   the echoed query in the page `<title>` and climbed to a page-chrome price, the
   same on every search. Lesson: capture the VALUE'S SOURCE (element or product
   name), and a uniform result usually means a broken extractor, not a source
   without data.
