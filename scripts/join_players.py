"""Join Understat and SofaScore players into one identity table.

Match order: alias (keyed by understat_id) -> normalized exact -> fuzzy.
Aliases are keyed by understat_id because two different players can share a name.
Writes processed/players.csv and processed/unmatched_players.csv.
"""
import re
import unicodedata

import pandas as pd
from rapidfuzz import fuzz, process

import config

ALIASES_PATH = config.DATA_DIR / "aliases.csv"
FUZZY_THRESHOLD = 95

TRANSLIT = {"ø": "o", "Ø": "o", "ð": "d", "Ð": "d", "þ": "th", "Þ": "th",
            "ł": "l", "Ł": "l", "æ": "ae", "Æ": "ae", "œ": "oe", "ß": "ss"}


def normalize(name):
    name = str(name)
    for src, dst in TRANSLIT.items():
        name = name.replace(src, dst)
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    name = re.sub(r"[^a-z ]", " ", name.lower())
    return " ".join(sorted(name.split()))


def load_aliases():
    if not ALIASES_PATH.exists():
        ALIASES_PATH.write_text("understat_id,understat_name,sofascore_name\n", encoding="utf-8")
    aliases = pd.read_csv(ALIASES_PATH, dtype={"understat_id": str}).fillna("")
    return {str(r.understat_id): normalize(r.sofascore_name) for r in aliases.itertuples() if r.sofascore_name}


def main():
    understat = pd.read_csv(config.PROCESSED_DIR / "understat_players.csv", dtype={"understat_id": str})
    sofascore = pd.read_csv(config.PROCESSED_DIR / "sofascore_players.csv", dtype={"sofascore_id": str})
    understat["norm"] = understat["player"].map(normalize)
    sofascore["norm"] = sofascore["player"].map(normalize)
    aliases = load_aliases()

    s_display = {r["norm"]: r["player"] for _, r in sofascore.iterrows()}
    s_id = {r["norm"]: r["sofascore_id"] for _, r in sofascore.iterrows()}

    pairs = {}
    unmatched = []
    for season, ug in understat.groupby("season"):
        by_norm = {r["norm"]: r for _, r in sofascore[sofascore["season"] == season].iterrows()}
        s_norms = list(by_norm)

        for _, urow in ug.iterrows():
            uid = urow["understat_id"]
            alias_target = aliases.get(uid)

            s_name, s_sid = None, None
            if alias_target and alias_target in s_id:
                s_name, s_sid = s_display[alias_target], s_id[alias_target]
            else:
                target = urow["norm"]
                if target in by_norm:
                    s_name, s_sid = by_norm[target]["player"], by_norm[target]["sofascore_id"]
                else:
                    best = process.extractOne(target, s_norms, scorer=fuzz.token_sort_ratio)
                    if best and best[1] >= FUZZY_THRESHOLD:
                        s_name, s_sid = by_norm[best[0]]["player"], by_norm[best[0]]["sofascore_id"]

            if s_sid is not None:
                pairs[(uid, s_sid)] = (urow["player"], s_name)
            else:
                cand = process.extractOne(urow["norm"], list(s_display), scorer=fuzz.WRatio)
                unmatched.append(
                    {
                        "season": season,
                        "understat_id": uid,
                        "understat_name": urow["player"],
                        "suggested_sofascore_name": s_display.get(cand[0], "") if cand else "",
                        "suggestion_score": round(cand[1], 1) if cand else 0,
                    }
                )

    players = pd.DataFrame(
        [{"understat_id": u, "understat_name": un, "sofascore_id": s, "sofascore_name": sn}
         for (u, s), (un, sn) in pairs.items()]
    ).sort_values("understat_id")

    players.to_csv(config.PROCESSED_DIR / "players.csv", index=False, encoding="utf-8")
    un_df = pd.DataFrame(unmatched)
    un_df.to_csv(config.PROCESSED_DIR / "unmatched_players.csv", index=False, encoding="utf-8")

    total = understat["understat_id"].nunique()
    matched = players["understat_id"].nunique()
    print(f"Understat players: {total}")
    print(f"Matched (unique players): {matched} ({matched / total:.1%})")
    print(f"Unique unmatched understat_ids: {un_df['understat_id'].nunique()}")
    print(f"Unmatched season-rows: {len(un_df)} -> {config.PROCESSED_DIR / 'unmatched_players.csv'}")


if __name__ == "__main__":
    main()
