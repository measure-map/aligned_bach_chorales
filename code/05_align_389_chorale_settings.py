# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.16.4
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %% [markdown]
# # Aligning the 389 chorale settings with the 371 Riemenschneider chorales
#
# This script can be run as standalone or, if Jupyter with [Jupytext](https://jupytext.readthedocs.io/) extension are
# installed, opened as a Jupyter notebook.
#
# The 389 chorale settings (*389 Choralgesänge*, Breitkopf ed. nr. 3765, typeset with lyrics by Gertim Alberda,
# submodule `389_chorale_settings`) are named `B001`–`B389` after that edition, which orders the chorales
# alphabetically by melody. The previous notebooks have aligned the three datasets of the 371 chorales (`krn`, `cap`,
# `xml`) with the Riemenschneider numbering (`aligned_files.csv`). This notebook links each `B###` to the
# Riemenschneider collection and documents every step, so that the result can be reviewed. It proceeds in three stages:
#
# 1. **Metadata** (sections 1–4): `B###` → BWV number with movement → row of the bach-chorales.com table → one or
#    several Riemenschneider numbers. Cross-checked against Mark Gotham's metadata and against the manually corrected
#    Wikipedia table (`mapping_table_manually_corrected.csv`).
# 2. **Pitch-class vectors** (sections 5–6): every proposed pair `(B###, R)` is checked by comparing the music;
#    settings without a metadata match are matched to the nearest Riemenschneider chorale if it is close enough.
# 3. **Measure maps** (sections 7–9): the measure maps of the 389 are compared with those of all three
#    Riemenschneider datasets using the new layered comparison of pyMeasureMap.
#
# Section 10 lists the open problems.
#
# **Requirements**
#
# * The submodule `389_chorale_settings` at tag `v2.4` (or later). Earlier versions lack the BWV numbers in the
#   `workTitle` metadata field, which this notebook depends on. (The notes and measures tables are the same as in the
#   previously checked out commit.)
# * pyMeasureMap with the layered comparison (`pymeasuremap.compare.compare_layered`), i.e., the branch
#   `layered-compare`, which builds on `development`.
#
# **Outputs**
#
# * `concordance_389.csv`: one row per `B###`, with the evidence and a `confidence` column;
# * `concordance_389_pcv_check.csv`: one row per proposed `(B###, R)` pair with its PCV distances;
# * `../data/389_chorale_settings/measuremaps/B###.mm.json`: measure maps of the 389, converted from ms3's measures
#   tables;
# * `comparison_389/<dataset>/`: for each of `krn`, `cap`, `xml`, the summary `comparison_summary.tsv` and, for each
#   pair that is not identical, a text report (`.txt`) and a measure-by-measure table (`.tsv`).

# %%
import io
import json
import os
import re
import unicodedata
from difflib import SequenceMatcher
from fractions import Fraction
from typing import List, Optional

import numpy as np
import pandas as pd
from IPython.display import display

pd.set_option("display.max_rows", 500)
pd.set_option("display.max_columns", 50)
pd.set_option("display.max_colwidth", 80)

DATASET_389 = os.path.abspath("../389_chorale_settings/vocal_parts_only")
GOTHAM_CHORALES = os.path.abspath("../MarkGotham_xml/Bach,_Johann_Sebastian/Chorales")
NOTES_KRN = os.path.abspath("../data/craigsapp_krn/notes")
NOTES_CAP = os.path.abspath("../data/DCMLab_cap/notes")
NOTES_XML = os.path.abspath("../data/MarkGotham_xml/notes")
MM_389 = os.path.abspath("../data/389_chorale_settings/measuremaps")
COMPARISON_OUTPUT = os.path.abspath("comparison_389")

# %% [markdown]
# ## 1. Input tables
#
# ### 1.1 The bach-chorales.com table
#
# As in `01_prepare_metadata.py`, the main metadata table is the one from
# http://www.bach-chorales.com/BachChoraleTable.htm, stored in `BCT_html_source`. Each row is one setting with its
# BWV number (including the movement, e.g. `153.1`) and its numbers in several collections. Where the Riemenschneider
# collection contains the same music more than once, the column `R` lists several numbers separated by `=`
# (e.g. `156 =308`); the same holds for the `B` column (Breitkopf numbering of the 371, *not* the 389!) and for `BWV`.

# %%
def split_alternatives(value) -> List[str]:
    """'86 =195 =305' -> ['86', '195', '305']"""
    if pd.isna(value):
        return []
    return [v.strip() for v in str(value).replace("(", "").replace(")", "").split("=") if v.strip()]


def base_bwv(bwv: str) -> str:
    """'153.1' -> '153', '145a' -> '145a', 'Anh.31' -> 'Anh.31'"""
    bwv = bwv.replace(" ", "")
    if bwv.startswith("Anh"):
        return bwv
    return bwv.split(".")[0].replace("-", "")


with open("BCT_html_source", encoding="utf-8") as f:
    bct = pd.read_html(io.StringIO(f.read()), na_values=["9999", "ZZZZ"], attrs=dict(id="sortable"))[0]
bct = bct.dropna(how="all").reset_index(drop=True)
bct["bwv_list"] = bct.BWV.map(split_alternatives)
bct["bwv"] = bct.bwv_list.map(lambda L: L[0] if L else pd.NA)
bct["bwv_base"] = bct.bwv.map(lambda b: base_bwv(b) if isinstance(b, str) else pd.NA)
bct["R_list"] = bct.R.map(lambda v: [int(x.split(".")[0]) for x in split_alternatives(v)])
print(f"{len(bct)} rows, {bct.R_list.map(bool).sum()} of which have a Riemenschneider number.")
bct[["BWV", "bwv", "bwv_base", "R", "R_list", "Text", "Tune"]].head(10)

# %% [markdown]
# ### 1.2 The metadata of the 389
#
# The BWV number is not stored in a dedicated field but appears in free text, mostly in `workTitle`
# (e.g. `Kantate, BWV 48 "Ich elender Mensch, wer wird mich erlösen": III. Choral "Solls ja so sein, daß Straf und
# Pein"`), sometimes in `subtitle_text` (e.g. `(Bach-Ausgabe Bd. 39, Choräle No.1, BWV 253)`). For movements of larger
# works, the movement is given in various forms: Roman numerals (cantatas), `No. ##` (passions, oratorios), or a
# letter (`a. Choral`, denoting e.g. BWV 145a). The function below extracts the base BWV number and, if present, the
# movement number. The text incipit is taken from `movementTitle` or, if missing, from `title_text`.

# %%
ROMAN = dict(I=1, V=5, X=10, L=50, C=100)


def roman_to_int(s: str) -> int:
    total, prev = 0, 0
    for ch in reversed(s):
        val = ROMAN[ch]
        total = total - val if val < prev else total + val
        prev = max(prev, val)
    return total


def extract_bwv_and_movement(work_title, subtitle):
    """Returns (bwv_base, movement_hint) where movement_hint is an int or None."""
    for text in (work_title, subtitle):
        if pd.isna(text):
            continue
        m = re.search(r"BWV\s*(Anh\.\s*\d+|\d+[a-z]?)(?:[./](\d+))?", text)
        if not m:
            continue
        bwv = m.group(1).replace(" ", "")
        movement = int(m.group(2)) if m.group(2) else None
        if movement is None:
            # Roman numeral or 'No. 15' after the colon, e.g. ': III. Choral', ': Teil II. No. 15 Choral'
            after = text.split(":", 1)[1] if ":" in text else ""
            no = re.search(r"No\.\s*(\d+)", after)
            rom = re.search(r"\b([IVXLC]+)\.\s*(?:Chora|Corale)", after)
            letter = re.search(r"(?:^|\s)([a-z])\.\s*Chora", after)
            if letter:
                # e.g. 'BWV 145 ... a. Chorale' denotes BWV 145a
                bwv += letter.group(1)
            elif no:
                movement = int(no.group(1))
            elif rom:
                movement = roman_to_int(rom.group(1))
        return bwv, movement
    return None, None


meta389 = pd.read_csv(os.path.join(DATASET_389, "metadata.tsv"), sep="\t").set_index("piece")
assert meta389.workTitle.notna().sum() > 300, (
    "The workTitle field is mostly empty. Please check out the submodule 389_chorale_settings at tag v2.4 or later."
)
bwv_mvt = [extract_bwv_and_movement(w, s) for w, s in zip(meta389.workTitle, meta389.subtitle_text)]
meta389["bwv_base"] = [b for b, _ in bwv_mvt]
meta389["movement_hint"] = pd.array([m for _, m in bwv_mvt], dtype="Int64")
meta389["incipit"] = meta389.movementTitle.fillna(
    meta389.title_text.str.replace(r"^\d+\.\s*", "", regex=True)
).str.replace("\r\n", "\n")  # line breaks in the TSV may have been converted by git on Windows
print(f"{len(meta389)} settings; BWV number found for {meta389.bwv_base.notna().sum()}, "
      f"movement number found for {meta389.movement_hint.notna().sum()}.")
meta389[["workTitle", "bwv_base", "movement_hint", "incipit"]].head(10)

# %% [markdown]
# Settings for which no BWV number could be extracted:

# %%
meta389.loc[meta389.bwv_base.isna(), ["workTitle", "subtitle_text", "incipit"]]

# %% [markdown]
# A sample of titles from which a movement number was extracted, to check the different notations:

# %%
with_movement = meta389[meta389.movement_hint.notna()]
with_movement.groupby(with_movement.workTitle.str.extract(r"^(\w+)", expand=False)).head(2)[
    ["workTitle", "bwv_base", "movement_hint"]
]


# %% [markdown]
# ## 2. Matching each setting to a row of the bach-chorales.com table
#
# For each setting, the candidates are all rows of the table with the same base BWV number. Then:
#
# * `unique_bwv`: there is only one candidate (typically the chorales without context, BWV 253–438);
# * `movement+text`: several candidates, exactly one with the extracted movement number, and its text incipit is
#   (nearly) as similar as the best one;
# * `movement_only(text_disagrees)`: as before, but another candidate has a clearly more similar text;
# * `text_only`: no usable movement number; the candidate with the most similar text (or melody title) is chosen;
# * `bwv_not_in_table`, `no_bwv`: no candidate.
#
# Text similarity is computed on the first 30 characters of the normalized incipits (lower case, no punctuation,
# no diacritics, no stanza numbers) with `difflib.SequenceMatcher`. Since a setting's incipit can refer to the lyrics
# or to the melody, both the `Text` and the `Tune` column are tried.

# %%
def normalize_text(text) -> str:
    if pd.isna(text):
        return ""
    text = re.sub(r"\(\d+\)", "", str(text))  # stanza numbers
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if c.isalnum() or c == " ")
    text = text.replace("ß", "ss")
    return re.sub(r"\s+", " ", text).strip()


def text_similarity(a, b) -> float:
    a, b = normalize_text(a), normalize_text(b)
    if not a or not b:
        return 0.0
    n = min(len(a), len(b), 30)
    return SequenceMatcher(None, a[:n], b[:n]).ratio()


def movement_of(bwv: str) -> Optional[int]:
    parts = bwv.split(".")
    if len(parts) > 1 and parts[-1].isdigit():
        return int(parts[-1])
    return None


def match_piece(row) -> dict:
    result = dict(bct_row=pd.NA, bwv=pd.NA, method="no_bwv", n_candidates=0, text_sim=pd.NA)
    if row.bwv_base is None:
        return result
    candidates = bct[bct.bwv_base == base_bwv(row.bwv_base)]
    result["n_candidates"] = len(candidates)
    if len(candidates) == 0:
        result["method"] = "bwv_not_in_table"
        return result
    sims = candidates.apply(
        lambda c: max(text_similarity(row.incipit, c.Text), text_similarity(row.incipit, c.Tune)), axis=1
    )
    if len(candidates) == 1:
        choice, method = candidates.index[0], "unique_bwv"
    else:
        by_movement = (
            candidates[candidates.bwv.map(movement_of) == row.movement_hint]
            if pd.notna(row.movement_hint)
            else candidates.iloc[:0]
        )
        best_text = sims.idxmax()
        if len(by_movement) == 1 and sims[by_movement.index[0]] >= sims.max() - 0.05:
            choice, method = by_movement.index[0], "movement+text"
        elif len(by_movement) == 1:
            choice, method = by_movement.index[0], "movement_only(text_disagrees)"
        else:
            choice, method = best_text, "text_only"
    result.update(bct_row=choice, bwv=bct.at[choice, "bwv"], method=method, text_sim=round(sims[choice], 2))
    return result


matches = pd.DataFrame([match_piece(row) for row in meta389.itertuples()], index=meta389.index)
matches["R"] = matches.bct_row.map(lambda i: bct.at[i, "R_list"] if pd.notna(i) else [])
matches["bct_text"] = matches.bct_row.map(lambda i: bct.at[i, "Text"] if pd.notna(i) else pd.NA)
matches.method.value_counts()

# %% [markdown]
# The matches that were not decided by a unique BWV number or by movement and text together deserve a look:

# %%
uncertain = matches.method.isin(["text_only", "movement_only(text_disagrees)", "bwv_not_in_table", "no_bwv"])
pd.concat([meta389.loc[uncertain, ["incipit", "workTitle"]], matches.loc[uncertain, ["method", "bwv", "bct_text", "text_sim", "R"]]], axis=1)

# %% [markdown]
# Matches with a low text similarity (< 0.5), which may hint at a wrong row (or simply at a setting whose incipit
# refers to the melody rather than to the stanza):

# %%
low_sim = matches.text_sim.map(lambda x: pd.notna(x) and x < 0.5).astype(bool)
pd.concat([meta389.loc[low_sim, ["incipit"]], matches.loc[low_sim, ["method", "bwv", "bct_text", "text_sim", "R"]]], axis=1)

# %% [markdown]
# How many Riemenschneider numbers does each setting get? Several numbers mean that the Riemenschneider collection
# contains the same music twice (e.g. B008 ↔ R. 156 = R. 308).

# %%
matches.R.map(len).value_counts().sort_index().rename("n_settings").rename_axis("n_R")


# %% [markdown]
# ## 3. Cross-check with Mark Gotham's metadata
#
# Each chorale folder in `MarkGotham_xml` contains a `metadata.json` that maps the Riemenschneider number to a BWV
# number independently of the bach-chorales.com table. For each match, we check whether the BWV number from the table
# equals (one of) the BWV numbers that Gotham's metadata gives for the proposed Riemenschneider number(s).

# %%
gotham = {}
for folder in sorted(os.listdir(GOTHAM_CHORALES)):
    path = os.path.join(GOTHAM_CHORALES, folder, "metadata.json")
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            md = json.load(f)
        gotham[int(md["Riemenschneider"])] = dict(md)
gotham = pd.DataFrame.from_dict(gotham, orient="index").sort_index()


def normalize_bwv(bwv) -> str:
    """Make '248.12-2', '145-a', '117.4 =117.9' comparable."""
    if pd.isna(bwv):
        return ""
    bwv = str(bwv).split("=")[0].strip().strip("()")
    bwv = re.sub(r"-\d+$", "", bwv).replace("-", "")
    parts = bwv.split(".")
    if len(parts) > 1 and parts[-1].isdigit():
        parts[-1] = str(int(parts[-1]))
    return ".".join(parts)


def gotham_agrees(row) -> object:
    if not row.R:
        return pd.NA
    gotham_bwvs = {normalize_bwv(gotham.BWV.get(r)) for r in row.R}
    return normalize_bwv(row.bwv) in gotham_bwvs


matches["gotham_agrees"] = matches.apply(gotham_agrees, axis=1)
matches.gotham_agrees.value_counts(dropna=False)

# %% [markdown]
# Disagreements:

# %%
disagree = matches.gotham_agrees.eq(False).fillna(False).astype(bool)
pd.concat([
    meta389.loc[disagree, ["incipit"]],
    matches.loc[disagree, ["bwv", "R"]],
    matches.loc[disagree, "R"].map(lambda L: [gotham.BWV.get(r) for r in L]).rename("gotham_BWV"),
], axis=1)


# %% [markdown]
# ## 4. Preliminary (metadata-only) concordance
#
# The metadata confidence is
#
# * `high`: unique BWV or movement + text, Gotham does not disagree, and text similarity ≥ 0.5;
# * `check_text`: like `high` but with a low text similarity;
# * `check`: decided by text or movement alone, or Gotham disagrees;
# * `none`: no row found.

# %%
def metadata_confidence(row) -> str:
    if pd.isna(row.bwv):
        return "none"
    if row.method in ("unique_bwv", "movement+text") and row.gotham_agrees is not False:
        return "high" if (pd.isna(row.text_sim) or row.text_sim >= 0.5) else "check_text"
    return "check"


concordance = pd.concat([
    meta389[["incipit", "workTitle"]],
    matches[["bwv", "R", "method", "n_candidates", "text_sim", "gotham_agrees", "bct_text"]],
], axis=1)
concordance["confidence"] = matches.apply(metadata_confidence, axis=1)
concordance["R"] = concordance.R.map(lambda L: ";".join(str(r) for r in L))
concordance.index.name = "B389"
concordance.confidence.value_counts()

# %% [markdown]
# ### 4.1 Riemenschneider chorales without a counterpart among the 389

# %%
covered = {int(r) for rs in concordance.R if rs for r in rs.split(";")}
missing_R = sorted(set(range(1, 372)) - covered)
print(f"{len(covered)} Riemenschneider numbers are covered, {len(missing_R)} are not.")
gotham.loc[missing_R, ["text", "BWV"]]

# %% [markdown]
# ### 4.2 Cross-check with the manually corrected Wikipedia table
#
# `mapping_table_manually_corrected.csv` (work in progress on this branch) merges `riemenschneider.csv` with the
# table from [Wikipedia](https://en.wikipedia.org/wiki/List_of_chorale_harmonisations_by_Johann_Sebastian_Bach)
# whose column `389` gives the number in the 389 collection. Its rows have been corrected by hand. It was not used
# for the concordance above, which makes it an independent check. Below, all `(B, R)` pairs from both sources are
# juxtaposed.

# %%
manual = pd.read_csv("mapping_table_manually_corrected.csv")
manual_pairs = (
    manual[["389", "Riemenschneider", "BWV"]]
    .dropna(subset=["389", "Riemenschneider"])
    .astype({"389": int, "Riemenschneider": int})
)
manual_pairs = set(zip(manual_pairs["389"].map(lambda n: f"B{n:03d}"), manual_pairs.Riemenschneider))
concordance_pairs = {(b, int(r)) for b, rs in concordance.R.items() if rs for r in rs.split(";")}
only_manual = sorted(manual_pairs - concordance_pairs)
only_concordance = sorted(concordance_pairs - manual_pairs)
print(f"{len(manual_pairs & concordance_pairs)} pairs in both, {len(only_manual)} only in the manual table, "
      f"{len(only_concordance)} only in the concordance.")


def describe_pairs(pairs) -> pd.DataFrame:
    df = pd.DataFrame(pairs, columns=["B389", "R"])
    df["incipit"] = df.B389.map(concordance.incipit)
    df["concordance_R"] = df.B389.map(concordance.R)
    df["manual_R"] = df.B389.map(
        lambda b: ";".join(str(r) for bb, r in sorted(manual_pairs) if bb == b)
    )
    df["gotham_text_of_R"] = df.R.map(gotham.text)
    df["gotham_BWV_of_R"] = df.R.map(gotham.BWV)
    df["bwv_of_B"] = df.B389.map(concordance.bwv)
    return df


def classify_disagreement(b: str, R: int, source: str) -> str:
    concordance_Rs = {int(r) for r in concordance.R[b].split(";")} if concordance.R[b] else set()
    manual_Rs = {r for bb, r in manual_pairs if bb == b}
    if not 1 <= R <= 371 or (manual_Rs and all(not 1 <= r <= 371 for r in manual_Rs)):
        return "manual: R out of range (typo?)"
    if source == "concordance" and manual_Rs and manual_Rs < concordance_Rs:
        return "duplicate R not listed in manual table"
    if source == "concordance" and not manual_Rs:
        return "manual table has no R for this setting"
    return "conflict"


disagreements = pd.concat([
    describe_pairs(only_manual).assign(source="manual"),
    describe_pairs(only_concordance).assign(source="concordance"),
], ignore_index=True)
disagreements["kind"] = [classify_disagreement(b, r, s) for b, r, s in disagreements[["B389", "R", "source"]].itertuples(index=False)]
disagreements.kind.value_counts()

# %% [markdown]
# The concordance lists all Riemenschneider numbers for the same music, whereas the manual table mostly links a
# `B###` only to one of them; those cases are not actual disagreements. The remaining ones:

# %%
real_disagreements = disagreements[disagreements.kind != "duplicate R not listed in manual table"]
real_disagreements


# %% [markdown]
# ## 5. Checking the matches with pitch-class vectors
#
# As in `02_make_pcvs.py`, a pitch-class vector (PCV) sums up the note durations per tonal pitch class (TPC).
# Unlike in `03_compare_pcvs.py`,
#
# * the vectors are normalized to sum to 1, so that a setting with written-out repeats remains comparable;
# * the distance is the minimal sum of absolute differences over all transpositions by up to 7 fifths, since the
#   editions may transpose settings. The transposition yielding the minimum is reported as `shift` (0 = same key,
#   1 = a fifth higher, etc.).
#
# Two vectors are computed per piece: for the whole piece (`full`) and for the notes with onsets within the first
# 12 quarter notes (`first12q`), which is independent of how the end of a piece is notated. (Counting quarter notes
# rather than measures makes this independent of how the anacrusis is encoded.)
#
# For the Riemenschneider side, the notes tables from `krn` are used, falling back to `cap` or `xml` if missing.

# %%
TPC_RANGE = range(-20, 21)


def read_notes(path: str) -> pd.DataFrame:
    return pd.read_csv(path, sep="\t", usecols=["mc", "mn", "quarterbeats", "duration_qb", "tpc"])


def pcv(notes: pd.DataFrame, n_quarters: Optional[float] = None) -> np.ndarray:
    """If n_quarters is given, only onsets within the first n_quarters quarter notes are counted."""
    if n_quarters:
        qb = notes.quarterbeats.map(lambda x: float(Fraction(str(x))) if pd.notna(x) else np.inf)
        notes = notes[qb < n_quarters]
    sums = notes.groupby("tpc").duration_qb.sum().reindex(TPC_RANGE, fill_value=0.0).to_numpy()
    total = sums.sum()
    return sums / total if total else sums


def pcv_distance(a: np.ndarray, b: np.ndarray, max_shift: int = 7):
    """Minimal L1 distance between a and b transposed by 'shift' fifths. Returns (distance, shift)."""
    best = (np.inf, 0)
    for shift in range(-max_shift, max_shift + 1):
        d = np.abs(np.roll(a, shift) - b).sum()
        if d < best[0] - 1e-9 or (abs(d - best[0]) < 1e-9 and abs(shift) < abs(best[1])):
            best = (d, shift)
    return round(float(best[0]), 3), -best[1]


notes_dir_389 = os.path.join(DATASET_389, "notes")
notes389 = {
    f.split(".")[0]: read_notes(os.path.join(notes_dir_389, f))
    for f in sorted(os.listdir(notes_dir_389))
    if f.endswith(".notes.tsv")
}
alignment = pd.read_csv("../aligned_files.csv", index_col=0)
notesR, notes_source = {}, {}
for R, row in alignment.iterrows():
    candidates = [
        ("krn", os.path.join(NOTES_KRN, row.krn_file.replace(".krn", ".notes.tsv")) if isinstance(row.krn_file, str) else None),
        ("cap", os.path.join(NOTES_CAP, row.cap_file.replace(".mscx", ".notes.tsv")) if isinstance(row.cap_file, str) else None),
        ("xml", os.path.join(NOTES_XML, row.xml_file.split("/")[0] + ".notes.tsv")),
    ]
    for source, path in candidates:
        if path and os.path.isfile(path):
            notesR[R], notes_source[R] = read_notes(path), source
            break
print(f"Notes for {len(notes389)} of the 389 and {len(notesR)} of the 371.")
print("Riemenschneider chorales for which krn could not be used:", {R: s for R, s in notes_source.items() if s != "krn"})

pcvs = {
    kind: (
        {b: pcv(df, n) for b, df in notes389.items()},
        {r: pcv(df, n) for r, df in notesR.items()},
    )
    for kind, n in (("full", None), ("first12q", 12))
}


def pcv_columns(b: str, R: int) -> dict:
    result = {}
    for kind, (vectors389, vectorsR) in pcvs.items():
        d, s = pcv_distance(vectorsR[R], vectors389[b])
        result[f"pcv_{kind}"] = d
        result[f"shift_{kind}"] = s
    return result


def nearest_R(b: str, kind: str = "full", n: int = 3) -> list:
    vectors389, vectorsR = pcvs[kind]
    dists = sorted((pcv_distance(v, vectors389[b])[0], R) for R, v in vectorsR.items())
    return dists[:n]


# %% [markdown]
# One row per `(B, R)` pair proposed by the metadata. In addition, for every setting, the nearest Riemenschneider
# chorale by full-piece PCV (`nearest_R`), so that wrong or missing metadata matches become visible.

# %%
pairs = []
for b, row in concordance.iterrows():
    nearest = nearest_R(b)
    base = dict(B389=b, incipit=row.incipit, bwv=row.bwv, confidence=row.confidence,
                nearest_R=nearest[0][1], nearest_dist=nearest[0][0])
    Rs = [int(r) for r in row.R.split(";")] if row.R else []
    if not Rs:
        pairs.append(dict(base, R=pd.NA))
        continue
    for R in Rs:
        pairs.append(dict(base, R=R, **pcv_columns(b, R)))
pairs = pd.DataFrame(pairs)
pairs.to_csv("concordance_389_pcv_check.csv", index=False, lineterminator="\n")
proposed_pairs = pairs.dropna(subset=["R"])
print(f"{len(proposed_pairs)} proposed pairs for {proposed_pairs.B389.nunique()} settings.")
proposed_pairs.head()

# %% [markdown]
# ### 5.1 Distribution of the distances
#
# For true matches, both distances should be close to 0. The quantiles show that the bulk of the pairs is
# practically identical, with a tail of larger distances:

# %%
proposed_pairs[["pcv_full", "pcv_first12q"]].describe(percentiles=[0.5, 0.75, 0.9, 0.95, 0.99]).round(3)

# %%
pd.cut(proposed_pairs.pcv_full, [-0.001, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 2]).value_counts().sort_index().rename("n_pairs")

# %% [markdown]
# Transpositions between the editions (shift in fifths, full piece):

# %%
proposed_pairs.shift_full.value_counts().sort_index()

# %% [markdown]
# ### 5.2 Pairs whose music diverges
#
# Proposed pairs with a full-piece distance > 0.05. Where `pcv_first12q` is (close to) 0, the beginnings agree and
# the difference is likely due to written-out repeats or a different ending; where it is large, the metadata
# match itself is questionable.

# %%
diverging = proposed_pairs[proposed_pairs.pcv_full > 0.05].sort_values("pcv_full")
diverging[["B389", "R", "incipit", "bwv", "confidence", "pcv_full", "pcv_first12q", "shift_full", "nearest_R", "nearest_dist"]]

# %% [markdown]
# ### 5.3 Settings whose nearest neighbour is not the proposed one
#
# If the nearest Riemenschneider chorale by PCV is not among the proposed ones, this can point to a wrong match, or
# simply to two very similar settings (e.g. the same melody harmonized twice in the same key).

# %%
nearest_differs = proposed_pairs.groupby("B389").apply(lambda df: df.nearest_R.iloc[0] not in set(df.R))
nd = proposed_pairs[proposed_pairs.B389.isin(nearest_differs[nearest_differs].index)]
nd[["B389", "R", "incipit", "pcv_full", "pcv_first12q", "nearest_R", "nearest_dist"]]


# %% [markdown]
# ## 6. Final concordance
#
# * `pcv_full_max`, `pcv_first12q_max`: the largest distances among the `(B, R)` pairs proposed by the metadata.
# * For settings without any metadata match, `pcv_candidate_R` proposes the nearest Riemenschneider chorale if its
#   full-piece distance is below `PCV_CANDIDATE_THRESHOLD`.
# * `nearest_R_differs`: the nearest Riemenschneider chorale by PCV is not among the proposed ones.
# * `metadata_confidence`: the confidence from section 4.
# * `confidence`:
#   * `high`: metadata match confirmed by the music (`pcv_full_max` ≤ 0.05);
#   * `check_pcv`: metadata match, but the music diverges (see section 5.2);
#   * `pcv_only`: no metadata match, but a very close Riemenschneider chorale by PCV;
#   * `not_in_R`: no counterpart in the Riemenschneider collection.

# %%
PCV_CANDIDATE_THRESHOLD = 0.04
proposed = proposed_pairs.groupby("B389")
concordance["pcv_full_max"] = proposed.pcv_full.max()
concordance["pcv_first12q_max"] = proposed.pcv_first12q.max()
concordance["nearest_R"] = pairs.groupby("B389").nearest_R.first()
concordance["nearest_dist"] = pairs.groupby("B389").nearest_dist.first()
concordance["nearest_R_differs"] = nearest_differs.reindex(concordance.index)
no_R = concordance.R == ""
concordance["pcv_candidate_R"] = pd.NA
candidate_mask = no_R & (concordance.nearest_dist < PCV_CANDIDATE_THRESHOLD)
concordance.loc[candidate_mask, "pcv_candidate_R"] = concordance.loc[candidate_mask, "nearest_R"]
concordance["metadata_confidence"] = concordance.confidence.where(~no_R)
concordance.loc[no_R, "confidence"] = "not_in_R"
concordance.loc[candidate_mask, "confidence"] = "pcv_only"
concordance.loc[~no_R, "confidence"] = "high"
concordance.loc[~no_R & (concordance.pcv_full_max > 0.05), "confidence"] = "check_pcv"
concordance.to_csv("concordance_389.csv", lineterminator="\n")
concordance.confidence.value_counts()

# %% [markdown]
# Cross-tabulation of the metadata confidence (rows) with the final confidence (columns):

# %%
pd.crosstab(concordance.metadata_confidence.fillna("none"), concordance.confidence, margins=True)

# %% [markdown]
# ### 6.1 Settings matched by the music only (`pcv_only`)
#
# These have no BWV-based match, but a Riemenschneider chorale with nearly the same pitch content. The nearest
# three Riemenschneider chorales are shown together with Gotham's metadata for the candidate:

# %%
pcv_only = concordance[concordance.confidence == "pcv_only"].copy()
pcv_only["nearest_3"] = [nearest_R(b) for b in pcv_only.index]
pcv_only["candidate_text"] = pcv_only.pcv_candidate_R.astype(int).map(gotham.text)
pcv_only["candidate_BWV"] = pcv_only.pcv_candidate_R.astype(int).map(gotham.BWV)
pcv_only[["incipit", "workTitle", "bwv", "pcv_candidate_R", "candidate_text", "candidate_BWV", "nearest_3"]]

# %% [markdown]
# ### 6.2 Settings without a counterpart (`not_in_R`)
#
# Including the distance to the nearest Riemenschneider chorale, to show that none is close:

# %%
not_in_R = concordance[concordance.confidence == "not_in_R"]
print(f"{len(not_in_R)} settings; smallest nearest distance: {not_in_R.nearest_dist.min()}")
not_in_R[["incipit", "workTitle", "bwv", "method", "nearest_R", "nearest_dist"]]


# %% [markdown]
# ## 7. Measure maps for the 389
#
# The measure maps are created from ms3's measures tables with pyMeasureMap's converter, i.e., through the same
# pipeline (MuseScore → ms3 measures table → measure map) as those for the three Riemenschneider datasets in
# `../data/*/measuremaps`. As a consequence, the field `count` corresponds to ms3's `mc` (counting every measure
# object from 1, including the anacrusis) and `number` to ms3's `mn` (where an anacrusis gets 0).

# %%
from pymeasuremap.base import MeasureMap
from pymeasuremap.convert import measures_tsv_filepath_to_measure_map

os.makedirs(MM_389, exist_ok=True)
measures_dir_389 = os.path.join(DATASET_389, "measures")
for f in sorted(os.listdir(measures_dir_389)):
    if not f.endswith(".measures.tsv"):
        continue
    mm = measures_tsv_filepath_to_measure_map(os.path.join(measures_dir_389, f))
    mm.to_json_file(os.path.join(MM_389, f.replace(".measures.tsv", ".mm.json")))
print(f"{len(os.listdir(MM_389))} measure maps in {MM_389}")
pd.DataFrame(MeasureMap.from_json_file(os.path.join(MM_389, "B001.mm.json")).to_dicts(verbose=False)).head()


# %% [markdown]
# ## 8. Layered comparison of the measure maps
#
# `pymeasuremap.compare.compare_layered(preferred, other)` compares two measure maps in four layers, each of which
# yields a status (`same`, `differs`, or `skipped`) and a message:
#
# 1. `count`: same number of measures? (Also reports the total durations.)
# 2. `fields`: if the counts are equal, the fields `qstamp`, `number`, `name`, `time_signature`, `nominal_length`,
#    `actual_length`, `start_repeat`, `end_repeat`, `volta`, and `next` are compared measure by measure.
#    Differences in `number` are reported as offset ranges (e.g. "+1 in 1–8"). Names that merely reflect the numbers
#    and `qstamp` differences that follow from earlier length differences are not reported separately.
# 3. `unfolded`: if the counts or the repeat structures differ, both sides are unfolded (repeats written out, using
#    `next` or, if absent, the repeat signs and voltas) and the sequences of measure lengths are compared.
# 4. `aligned`: if there is still no match, the sequences of measure lengths (folded and unfolded; the alignment
#    with fewer edits is kept) are aligned with an edit distance that allows, besides matches, for `join`s and
#    `split`s (two measures of one side add up to one of the other), length changes, insertions, and deletions.
#
# The verdict summarizes the layers, from most to least similar:
#
# | verdict | meaning |
# |---|---|
# | `identical` | same number of measures, all fields defined on both sides are identical |
# | `same_measures` | same number of measures with the same lengths and time signatures; other fields (e.g. numbering, repeats) differ |
# | `same_count_different_measures` | same number of measures, but some lengths or time signatures differ |
# | `same_when_unfolded` | different numbers of measures, but identical once unfolded (one side writes out repeats) |
# | `alignable` | same music, segmented differently: only joins and splits are needed |
# | `different` | the alignment requires insertions, deletions, or length changes |
#
# The 389 are treated as `preferred`; each of the three Riemenschneider datasets as `other`. All `(B, R)` pairs
# from the concordance are compared, including the `pcv_only` candidates.

# %%
from pymeasuremap.compare import compare_layered, compare_pairs

DATASETS = {
    "krn": (os.path.abspath("../data/craigsapp_krn/measuremaps"), lambda row: row.krn_file.replace(".krn", ".mm.json") if isinstance(row.krn_file, str) else None),
    "cap": (os.path.abspath("../data/DCMLab_cap/measuremaps"), lambda row: row.cap_file.replace(".mscx", ".mm.json") if isinstance(row.cap_file, str) else None),
    "xml": (os.path.abspath("../data/MarkGotham_xml/measuremaps"), lambda row: row.xml_file.split("/")[0] + ".mm.json"),
}

mm_pairs = []
for b, row in concordance.iterrows():
    if row.R:
        Rs = [int(r) for r in row.R.split(";")]
    elif pd.notna(row.pcv_candidate_R):
        Rs = [int(row.pcv_candidate_R)]
    else:
        continue
    for R in Rs:
        mm_pairs.append((b, R, row.confidence))
mm_pairs = pd.DataFrame(mm_pairs, columns=["B389", "R", "confidence"])
print(f"{len(mm_pairs)} (B, R) pairs to compare against each of the three datasets.")

# %% [markdown]
# Before running the whole corpus, an example of a full report: B072 vs R. 87 (`krn`), a pair that section 5.2
# flagged as diverging.

# %%
example = compare_layered(
    os.path.join(MM_389, "B072.mm.json"),
    os.path.join(DATASETS["krn"][0], DATASETS["krn"][1](alignment.loc[87])),
    preferred_name="B072",
    other_name="krn_R087",
)
print(example)

# %%
example.measure_table()

# %%
summaries = {}
for name, (directory, get_filename) in DATASETS.items():
    paths, names, keys = [], [], []
    for b, R, confidence in mm_pairs.itertuples(index=False):
        filename = get_filename(alignment.loc[R])
        path = os.path.join(directory, filename) if filename else None
        if path is None or not os.path.isfile(path):
            print(f"{name}: no measure map for R. {R}")
            continue
        paths.append((os.path.join(MM_389, f"{b}.mm.json"), path))
        names.append((b, f"{name}_R{R:03d}"))
        keys.append((b, R, confidence))
    summary, _ = compare_pairs(paths, names=names, output_directory=os.path.join(COMPARISON_OUTPUT, name))
    summary.index = pd.MultiIndex.from_tuples(keys, names=["B389", "R", "confidence"])
    summaries[name] = summary

# %% [markdown]
# ### 8.1 Verdicts per dataset

# %%
VERDICT_ORDER = ["identical", "same_measures", "same_count_different_measures", "same_when_unfolded", "alignable", "different", "error"]
verdicts = pd.concat({name: s.verdict.value_counts() for name, s in summaries.items()}, axis=1).fillna(0).astype(int)
verdicts = verdicts.reindex([v for v in VERDICT_ORDER if v in verdicts.index])
verdicts.to_csv(os.path.join(COMPARISON_OUTPUT, "verdicts.tsv"), sep="\t")
verdicts

# %% [markdown]
# ### 8.2 Which fields differ when the measures are the same?
#
# For the pairs with verdict `same_measures`, how often each field differs:

# %%
field_counts = pd.concat(
    {name: s.loc[s.verdict == "same_measures", "differing_fields"].str.split(", ").explode().value_counts()
     for name, s in summaries.items()},
    axis=1,
).fillna(0).astype(int)
field_counts

# %% [markdown]
# The most frequent numbering differences (offset segments as `(first count, last count, offset)`), here for
# `krn`. A constant `+1` means that the other dataset counts the anacrusis as measure 1.

# %%
summaries["krn"].loc[summaries["krn"].verdict == "same_measures", "message"].str.extract(
    r"measure numbers offset by ([^;|]+)", expand=False
).str.strip().value_counts().head(10)

# %% [markdown]
# ### 8.3 One example report per verdict (`krn`)

# %%
for verdict in VERDICT_ORDER[2:]:
    selection = summaries["krn"][summaries["krn"].verdict == verdict]
    if len(selection) == 0:
        continue
    b, R, _ = selection.index[0]
    report_path = os.path.join(COMPARISON_OUTPUT, "krn", f"{b}_vs_krn_R{R:03d}.txt")
    with open(report_path, encoding="utf-8") as f:
        print(f.read())

# %% [markdown]
# ### 8.4 All pairs that are not structurally the same in at least one dataset
#
# I.e., verdicts other than `identical` and `same_measures`. These are the cases where the editions differ in
# their barring, repeats, or content.

# %%
wide = pd.concat({name: s.verdict for name, s in summaries.items()}, axis=1)
structural = wide[~(wide.isin(["identical", "same_measures"]) | wide.isna()).all(axis=1)]
messages = summaries["krn"].message.reindex(structural.index)
structural.assign(krn_message=messages)

# %% [markdown]
# ### 8.5 Pairs whose verdict differs between the three datasets
#
# These point to encoding differences between the 371 datasets rather than between the two editions.

# %%
inconsistent = wide[wide.nunique(axis=1) > 1]
inconsistent.to_csv(os.path.join(COMPARISON_OUTPUT, "inconsistent_verdicts.tsv"), sep="\t")
print(f"{len(inconsistent)} of {len(wide)} pairs get different verdicts depending on the dataset.")
inconsistent.value_counts().head(15)


# %% [markdown]
# ## 9. Bringing the evidence together
#
# For the pairs flagged in section 5.2 (`check_pcv`) and section 6.1 (`pcv_only`), what do the measure maps say?

# %%
flagged = wide[wide.index.get_level_values("confidence").isin(["check_pcv", "pcv_only"])].copy()
flagged = flagged.join(
    proposed_pairs.set_index(["B389", "R"])[["pcv_full", "pcv_first12q"]].rename_axis(["B389", "R"]),
    on=["B389", "R"],
)
flagged["krn_message"] = summaries["krn"].message.reindex(flagged.index)
flagged

# %% [markdown]
# ## 10. Open problems
#
# **Summary of the result.** 329 of the 389 settings are matched by metadata and confirmed by the music, 12 are
# matched by metadata but their music diverges, 2 are matched by the music only, and 46 have no counterpart in the
# Riemenschneider collection. 7 Riemenschneider chorales have no counterpart among the 389.
#
# ### Decisions needed
#
# 1. **Are B165 and B340 the same settings as R. 345 and R. 293?** (§6.1) Their metadata point to different
#    movements than the Riemenschneider chorales, but the music is nearly identical (PCV 0.031 and 0.025, measure
#    maps `same_measures` in all three datasets):
#    * B165 is labelled BWV 248.64 (*Nun seid ihr wohl gerochen*), R. 345 is BWV 248.5 (*Wie soll ich dich
#      empfangen*), same tune. The manually corrected Wikipedia table supports B165 = BWV 248.5 = R. 345 (§4.2), so
#      the 389 metadata may be wrong here.
#    * B340 is labelled BWV 12.7, R. 293 is BWV 69a.6, both *Was Gott tut, das ist wohlgetan*.
#
#    If they are confirmed, R. 293 and R. 345 drop out of the list of Riemenschneider chorales missing from the 389.
# 2. **Disagreements with the manually corrected table** (§4.2):
#    * B317 is R. 47 in the manual table, but the 389 metadata say B316 = BWV 416 and B317 = BWV 245.5. The music
#      supports the concordance: B316–R. 47 has a PCV distance of 0.005, B317–R. 47 of 0.060. The manual table seems
#      to be off by one here.
#    * B147 has R. 384 in the manual table, which does not exist; the concordance has R. 284 (probably a typo).
#    * B204 has no Riemenschneider number in the manual table; the concordance proposes R. 11 (BWV 41.6, PCV 0.010).
#    * The concordance links settings to *all* Riemenschneider numbers with the same music (e.g. B008 ↔ R. 156 and
#      R. 308), whereas the manual table mostly lists one of them (23 cases). Which convention should the final
#      table follow?
#
# ### Pairs to inspect in the scores
#
# 3. **Same barring, different notes** (§5.2, §9): the measure maps agree, but the pitch content diverges already in
#    the first 12 quarter notes. Settings of the same tune have the same barring, so the measure maps cannot tell
#    them apart; these may be wrong matches or different versions:
#    * B223 ↔ R. 370 (BWV 74.8; `pcv_first12q` 0.257; nearest by PCV is R. 240),
#    * B161 ↔ R. 270 (BWV 161.6; 0.062; nearest is R. 8).
# 4. **Different music or notation** (§5.2, §8.4):
#    * B350 ↔ R. 150 (BWV 27.6, *Welt, ade!*): the largest PCV distance (0.223, first 12 quarters 0.392). R. 150 is
#      missing from `krn`; in `cap`/`xml`, the last 8 measures are notated in 12q measures in the 389 and split in two
#      in the Riemenschneider datasets, with 4 extra measures in the 389. Possibly a different version of the setting.
#    * B121 ↔ R. 130 (BWV 324, German Magnificat): barred differently (R. 130 contains a 16q measure); `different` in
#      all datasets.
#    * B329 ↔ R. 179 (BWV 140.7, *Wachet auf*): the 389 notate it in 2/2 with 36 measures, the Riemenschneider datasets
#      in 4/4 with 18. The PCVs agree, but the comparison reports 16 "length changes", which are actually time
#      signature mismatches (see 7.).
#    * The other pairs listed under 9. below: they get the verdict `same_count_different_measures`, `alignable`, or
#      `different` in at least one dataset (§8.4). Where the verdict depends on the dataset (e.g. B015 ↔ R. 359:
#      `different` for `krn`, `same_measures` for `cap`), the 371 datasets themselves disagree.
#    * Written-out repeats (`same_when_unfolded`, e.g. B072 ↔ R. 87) and different barring (`alignable`, e.g.
#      B205 ↔ R. 327, B330 ↔ R. 182, B177 ↔ R. 272) explain most of the remaining `check_pcv` cases; for B099, B291,
#      B306, and B376 the measure maps are (nearly) identical and the PCVs agree at the beginning, so the differences
#      are probably small editorial variants.
# 5. **Near-duplicates**: B313 (BWV 414) has a PCV distance of 0 to R. 177 (BWV 253, matched to B001) and 0.006 to
#    its own match R. 148. The two settings are known to be nearly identical (see the note "≈BWV 414" for BWV 253 in
#    the Wikipedia table, `mapping_table.csv`), so the PCV alone cannot decide between them (§5.3).
#
# ### Method and tooling
#
# 6. **Metadata parsing**: the BWV numbers are parsed from free text. 28 matches were not decided by BWV + movement
#    (§2), mostly because the incipits of the 389 name the melody (*Herzlich thut mich verlangen*) instead of the
#    stanza. They are all confirmed by the music, but a curated BWV/movement column in the 389 metadata would make
#    this step robust. This would also settle whether the metadata of B165 is correct.
# 7. **Layered compare** (pyMeasureMap):
#    * `change_length` is also reported when only the time signatures differ (B329), and its message says "different
#      length". Time signature mismatches should get their own operation, and proportional notation (2/2 with
#      doubled values vs. 4/4) could be detected as such.
#    * In alignments of unfolded sequences, the same count occurs several times (e.g. "preferred 8+3" for B177), which
#      is hard to read without the pass number.
#    * Most `same_measures` verdicts are due to `krn` and `cap` counting the anacrusis as measure 1 (§8.2). 95 of the
#      136 pairs whose verdict depends on the dataset are `same_measures` for `krn`/`cap` and `identical` for `xml`
#      (§8.5). These are numbering conventions of the 371 datasets, not differences between the editions.
# 8. **Missing data**: `cap` has no measure maps for 10 of the compared Riemenschneider chorales (they have no
#    `cap_file` in `aligned_files.csv`), `krn` none for R. 132 and R. 150.
# 9. **Final format**: the concordance (`concordance_389.csv`) has not yet been merged into `aligned_files.csv` or
#    the `mapping_table`; the 46 settings without counterpart need to be listed separately.
#
# The following cell lists all the cases mentioned above, generated from the results. For each problem, the
# relevant section is given.

# %%
check_pcv = concordance[concordance.confidence == "check_pcv"]
open_problems = {
    "1. Metadata matches where the music diverges (check_pcv, §5.2, §9)": check_pcv.index.tolist(),
    "2. Music-only matches without BWV agreement (pcv_only, §6.1)": [
        f"{b} ≈ R. {int(r)}" for b, r in pcv_only.pcv_candidate_R.items()
    ],
    "3. Matches not decided by BWV + movement (§2)": concordance.index[
        concordance.method.isin(["text_only", "movement_only(text_disagrees)"])
    ].tolist(),
    "4. Gotham's BWV disagrees (§3)": concordance.index[disagree].tolist(),
    "5. Disagreements with the manually corrected Wikipedia table (§4.2)": [
        f"{b}–R. {r} ({kind})" for b, r, kind in real_disagreements[["B389", "R", "kind"]].itertuples(index=False)
    ],
    "6. Riemenschneider chorales not among the 389 (§4.1)": [f"R. {r}" for r in missing_R],
    "7. Settings without a Riemenschneider counterpart (§6.2)": not_in_R.index.tolist(),
    "8. Nearest PCV neighbour differs from the match (§5.3)": nearest_differs[nearest_differs].index.tolist(),
    "9. Pairs that differ structurally in at least one dataset (§8.4)": [
        f"{b}–R. {r}" for b, r, _ in structural.index
    ],
}
for problem, items in open_problems.items():
    print(f"{problem}: {len(items)}")
    print("   ", ", ".join(map(str, items)) if items else "—")
