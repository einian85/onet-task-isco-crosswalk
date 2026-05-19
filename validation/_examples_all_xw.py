import re, pandas as pd
from pathlib import Path

def normalize_soc(v):
    if pd.isna(v): return None
    m = re.search(r"(\d{2})-(\d{4})", str(v))
    if m: return f"{m.group(1)}-{m.group(2)}"
    d = "".join(c for c in str(v) if c.isdigit())
    return f"{d[:2]}-{d[2:6]}" if len(d) >= 6 else None

def normalize_isco(v):
    if pd.isna(v): return None
    d = "".join(c for c in str(v) if c.isdigit())
    return d[:4] if len(d) >= 4 else None

MATCH_SCORE = {"exactMatch":1.0,"exactISCO":1.0,"narrowMatch":0.9,"closeMatch":0.75,"broadMatch":0.6}

def pipeline_top1(pred_path, tasks_path):
    pred = pd.read_csv(pred_path)
    tasks = pd.read_excel(tasks_path)[["Task ID","O*NET-SOC Code","Title"]]
    tasks.columns = ["task_id","soc_raw","soc_title"]
    tasks["soc_code"] = tasks["soc_raw"].map(normalize_soc)
    pred["task_id"] = pd.to_numeric(pred["task_id"], errors="coerce")
    pred["isco_code"] = pred["iscoGroup"].map(normalize_isco)
    pred = pred.dropna(subset=["isco_code"])
    m = pred.merge(tasks[["task_id","soc_code","soc_title"]], on="task_id", how="left").dropna(subset=["soc_code"])
    top1 = (m.groupby(["soc_code","isco_code"]).size().reset_index(name="n")
              .sort_values(["soc_code","n"], ascending=[True,False])
              .drop_duplicates("soc_code").rename(columns={"isco_code":"isco_imp"}))
    soc_titles = tasks[["soc_code","soc_title"]].drop_duplicates("soc_code")
    return top1.merge(soc_titles, on="soc_code", how="left")

isco_def = pd.read_excel("data/isco/ISCO-08 EN Structure and definitions.xlsx",
    sheet_name="ISCO-08 EN Struct and defin", usecols=["Level","ISCO 08 Code","Title EN"])
isco_title = dict(zip(
    isco_def[isco_def["Level"]==4]["ISCO 08 Code"].astype(str).str.zfill(4),
    isco_def[isco_def["Level"]==4]["Title EN"]
))

def show(label, top1, ref_sets, n=3):
    merged = top1.merge(ref_sets, on="soc_code", how="inner")
    merged["hit"] = merged.apply(lambda r: r["isco_imp"] in r["isco_ref_set"], axis=1)
    hits   = merged[merged["hit"]].sample(min(n, merged["hit"].sum()), random_state=7)
    misses = merged[~merged["hit"]].sample(min(n, (~merged["hit"]).sum()), random_state=7)
    rate   = merged["hit"].mean()
    print(f"\n{'='*72}")
    print(f"  {label}")
    print(f"  4-digit in-set rate: {rate:.1%}  |  n={len(merged)} SOC codes")
    print(f"{'='*72}")
    for kind, subset in [("HITS", hits), ("MISSES", misses)]:
        print(f"\n  --- {kind} ---")
        for _, row in subset.iterrows():
            imp_t = isco_title.get(row["isco_imp"], "?")
            ref_list = sorted(row["isco_ref_set"])
            ref_str = ", ".join(f"{c} {isco_title.get(c,'?')}" for c in ref_list[:3])
            if len(ref_list) > 3:
                ref_str += f"  (+{len(ref_list)-3} more)"
            print(f"    SOC {row['soc_code']}  {str(row.get('soc_title',''))[:45]}")
            print(f"      Pipeline → {row['isco_imp']}  {imp_t}")
            print(f"      Ref set  → {ref_str}")

top1_29 = pipeline_top1("output/ONET29_task_to_ISCO_crosswalk.csv",
                         "data/onet/29_2/Task Statements.xlsx")
top1_25 = pipeline_top1("output/ONET25_task_to_ISCO_crosswalk.csv",
                         "data/onet/25_0/Task Statements.xlsx")

# XW18.1
xw181 = pd.read_excel("data/crosswalks/ESCO_to_ONET-SOC.xlsx", sheet_name="Crosswalk")
xw181 = xw181.rename(columns={"SOC19-Code":"soc_raw","ESCO-Code":"isco_raw"})
xw181["soc_code"] = xw181["soc_raw"].map(normalize_soc)
xw181["isco_code"] = xw181["isco_raw"].map(normalize_isco)
ref181 = xw181.dropna(subset=["soc_code","isco_code"]).groupby("soc_code")["isco_code"].apply(set).reset_index().rename(columns={"isco_code":"isco_ref_set"})
show("XW18.1  ESCO→ONET-SOC  (SOC18, flat scores, many-to-many)", top1_29, ref181)

# XW18.2
xw182 = pd.read_csv("data/crosswalks/ONET_(Occupations)_0_updated.csv", skiprows=16)
xw182 = xw182.rename(columns={"O*NET Id":"soc_raw","Type of Match":"match_type"})
xw182["isco_direct"] = (xw182["ESCO or ISCO URI"]
    .where(xw182["ESCO or ISCO URI"].str.contains("/isco/", na=False))
    .str.extract(r"/C(\d{4})", expand=False))
esco_occ = pd.read_csv("data/esco/occupations_en.csv", usecols=["conceptUri","iscoGroup"]).dropna()
esco_occ["iscoGroup"] = pd.to_numeric(esco_occ["iscoGroup"].astype(str).str[:4], errors="coerce").dropna().astype(int).astype(str).str.zfill(4)
esco_occ = esco_occ.dropna(subset=["iscoGroup"]).rename(columns={"conceptUri":"ESCO or ISCO URI","iscoGroup":"isco_from_esco"})
xw182 = xw182.merge(esco_occ, on="ESCO or ISCO URI", how="left")
xw182["isco_raw"] = xw182["isco_direct"].combine_first(xw182["isco_from_esco"])
xw182["soc_code"] = xw182["soc_raw"].map(normalize_soc)
xw182["isco_code"] = xw182["isco_raw"].map(normalize_isco)
ref182 = xw182.dropna(subset=["soc_code","isco_code"]).groupby("soc_code")["isco_code"].apply(set).reset_index().rename(columns={"isco_code":"isco_ref_set"})
show("XW18.2  ONET-SOC→ESCO  (SOC18, typed scores, many-to-many)", top1_29, ref182)

# XW10.1
xw101 = pd.read_csv("data/crosswalks/esco_onet_crosswalk.csv")
xw101["soc_code"] = xw101["onet_code"].map(normalize_soc)
xw101["isco_code"] = xw101["isco_code"].map(normalize_isco)
ref101 = xw101.dropna(subset=["soc_code","isco_code"]).groupby("soc_code")["isco_code"].apply(set).reset_index().rename(columns={"isco_code":"isco_ref_set"})
show("XW10.1  ESCO-ONET MHV  (SOC10, semantic similarity scores)", top1_25, ref101)

# XW10.2
xw102 = pd.read_excel("data/crosswalks/isco_soc_crosswalk.xls", sheet_name="Data")
xw102.columns = [c.strip().lower().replace("-","_").replace(" ","_") for c in xw102.columns]
xw102["soc_code"] = xw102["2010_soc_code"].map(normalize_soc)
xw102["isco_code"] = xw102["isco_08_code"].map(normalize_isco)
ref102 = xw102.dropna(subset=["soc_code","isco_code"]).groupby("soc_code")["isco_code"].apply(set).reset_index().rename(columns={"isco_code":"isco_ref_set"})
show("XW10.2  BLS ISCO-SOC   (SOC10, official, typically 1-to-1)", top1_25, ref102)
