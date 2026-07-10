"""Compute 95% Wilson confidence intervals for key validation statistics."""
import math

def wilson_ci(p, n, z=1.96):
    """Wilson score interval for a proportion."""
    center = (p + z**2 / (2*n)) / (1 + z**2 / n)
    margin = (z / (1 + z**2 / n)) * math.sqrt(p*(1-p)/n + z**2/(4*n**2))
    return round((center - margin)*100, 1), round((center + margin)*100, 1)

def show(label, p, n):
    lo, hi = wilson_ci(p/100, n)
    print(f"  {label:<45}  {p:.1f}%  [{lo:.1f}%, {hi:.1f}%]  (±{(hi-lo)/2:.1f} pp)  n={n:,}")

print("O*NET 29.2  —  scenario A4 (lenient union, SOC 2018)  —  n covered = 18,755")
n_a4 = 18755   # tasks in crosswalk (coverage = 99.9% of 18,796)
show("Exact 4-digit",   81.7, n_a4)
show("Sub-major 2-digit", 90.1, n_a4)
show("Major group 1-digit", 94.2, n_a4)

print()
print("Cross-version agreement (O*NET 29.2 vs 25.0)  —  n = 16,049")
n_xv = 16049
show("Same ISCO-08 assignment", 97.7, n_xv)

print()
print("Author annotation  —  n = 108 tasks")
n_ann = 108
show("Exact 4-digit",     54.6, n_ann)
show("Sub-major 2-digit", 71.3, n_ann)
show("Major group 1-digit", 81.5, n_ann)

print()
print("SOC 2010  —  scenario B3 (lenient union)  —  representative release O*NET 25.0")
n_b3 = 19735   # approx tasks for O*NET 25.0
show("Exact 4-digit",   63.2, n_b3)
show("Major group",     82.8, n_b3)
