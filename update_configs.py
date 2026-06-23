"""
update_configs.py
Updates all config_onet*.yaml files with sweep-selected weight parameters.
Selected candidate: jf_d030_s675_i80_t60_o60
"""
import re
from pathlib import Path

BASE = Path(__file__).parent
configs = sorted(BASE.glob("configs/config_onet*.yaml"))

REPLACEMENTS = {
    r"w_soc_title:\s+[\d.]+": "w_soc_title: 0.675  ",
    r"w_dwa:\s+[\d.]+": "w_dwa: 0.030      ",
    r"w_isco:\s+[\d.]+": "w_isco: 0.80      ",
    r"w_isco_task:\s+[\d.]+": "w_isco_task: 0.60  ",
    r"w_occ:\s+[\d.]+": "w_occ: 0.60       ",
}

updated = []
skipped = []

for cfg_path in configs:
    text = cfg_path.read_text(encoding="utf-8")
    new_text = text
    for pattern, replacement in REPLACEMENTS.items():
        new_text = re.sub(pattern, replacement, new_text)
    if new_text != text:
        cfg_path.write_text(new_text, encoding="utf-8")
        updated.append(cfg_path.name)
    else:
        skipped.append(cfg_path.name)

print(f"Updated: {len(updated)} files")
print(f"Unchanged: {len(skipped)} files")
if skipped:
    print("Skipped:", skipped[:5])
