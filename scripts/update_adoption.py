#!/usr/bin/env python3
"""Refresh _data/adoption.json with live npm + NuGet download totals for the
Chartboost Mediation ecosystem (mediation + core SDKs, 17 adapters, Unity tools).

npm has no all-time endpoint, so we sum yearly point-download queries.
NuGet exposes cumulative totalDownloads via its search API.
Run from the repo root: python scripts/update_adoption.py
"""
import json, urllib.request, time, datetime, sys

# (display label, npm adapter suffix, NuGet id suffix)
ADAPTERS = [
    ("AdMob", "admob", "AdMob"),
    ("Google Bidding", "google-bidding", "GoogleBidding"),
    ("ironSource", "ironsource", "IronSource"),
    ("Pangle", "pangle", "Pangle"),
    ("AppLovin", "applovin", "AppLovin"),
    ("BidMachine", "bidmachine", "BidMachine"),
    ("Chartboost", "chartboost", "Chartboost"),
    ("Amazon APS", "amazon-publisher-services", "AmazonPublisherServices"),
    ("Verve", "verve", "Verve"),
    ("InMobi", "inmobi", "InMobi"),
    ("Meta", "meta-audience-network", "MetaAudienceNetwork"),
    ("Vungle", "vungle", "Vungle"),
    ("Unity Ads", "unity-ads", "UnityAds"),
    ("MobileFuse", "mobilefuse", "MobileFuse"),
    ("Mintegral", "mintegral", "Mintegral"),
    ("Digital Turbine", "digital-turbine-exchange", "DigitalTurbineExchange"),
    ("HyprMX", "hyprmx", "HyprMX"),
]
# core SDK + consent adapters + Unity utility packages (counted in totals, not the treemap)
NPM_OTHERS = [
    "com.chartboost.core",
    "com.chartboost.core.consent.google-user-messaging-platform",
    "com.chartboost.core.consent.unmanaged",
    "com.chartboost.core.consent.usercentrics",
    "com.chartboost.unity.logging",
    "com.chartboost.unity.threading",
    "com.chartboost.unity.utilities",
    "com.chartboost.unity.utilities.google",
]

def fetch(url):
    for _ in range(6):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "adoption-stats-bot"})
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.load(r)
        except Exception:
            time.sleep(1.0)
    return None

def npm_alltime(pkg):
    total = 0
    for y in range(2021, datetime.date.today().year + 1):
        d = fetch("https://api.npmjs.org/downloads/point/%d-01-01:%d-12-31/%s" % (y, y, pkg))
        if d and isinstance(d.get("downloads"), int):
            total += d["downloads"]
    return total

def kfloor(n):
    return (str(n // 1000) + "K") if n >= 1000 else str(n)

def kround(n):
    return (str(round(n / 1000)) + "K") if n >= 1000 else str(n)

def commas(n):
    return "{:,}".format(n)

# ---- npm ----
npm_med = npm_alltime("com.chartboost.mediation")
npm_tree = [["Mediation SDK", npm_med, 1]]
npm_ad_sum = 0
for label, suf, _ in ADAPTERS:
    v = npm_alltime("com.chartboost.mediation.unity.adapter." + suf)
    npm_ad_sum += v
    npm_tree.append([label, v, 0])
npm_others = sum(npm_alltime(p) for p in NPM_OTHERS)
npm_total = npm_med + npm_ad_sum + npm_others

# ---- NuGet ----
data = fetch("https://azuresearch-usnc.nuget.org/query?q=Chartboost.CSharp&take=100&prerelease=true")
nug = {}
if data:
    for p in data.get("data", []):
        pid = p.get("id", "")
        if pid.lower().startswith("chartboost.csharp"):
            nug[pid.lower()] = p.get("totalDownloads", 0)
nuget_total = sum(nug.values())
nug_med = nug.get("chartboost.csharp.mediation.unity", 0)
nuget_tree = [["Mediation SDK", nug_med, 1]]
nug_ad_sum = 0
for label, _, nid in ADAPTERS:
    v = nug.get(("Chartboost.CSharp.Mediation.Unity.Adapter." + nid).lower(), 0)
    nug_ad_sum += v
    nuget_tree.append([label, v, 0])
nuget_others = nuget_total - nug_med - nug_ad_sum

npm_tree.sort(key=lambda x: -x[1])
nuget_tree.sort(key=lambda x: -x[1])
grand = npm_total + nuget_total

# ---- sanity guard: never publish a failed/partial fetch ----
if npm_total < 150000 or nuget_total < 100000 or nug_med == 0:
    print("Sanity check FAILED (npm=%d nuget=%d med=%d) — not writing." % (npm_total, nuget_total, nug_med))
    sys.exit(1)

out = {
    "updated": datetime.date.today().isoformat(),
    "packages": 1 + len(ADAPTERS) + len(NPM_OTHERS),
    "total_display": kfloor(grand) + "+",
    "npm_display": kfloor(npm_total) + "+",
    "nuget_display": kfloor(nuget_total) + "+",
    "npm_adapters_display": commas(npm_ad_sum),
    "npm_extras_display": "~" + kround(npm_others),
    "nuget_adapters_display": commas(nug_ad_sum),
    "nuget_extras_display": "~" + kround(nuget_others),
    "npm_tree": npm_tree,
    "nuget_tree": nuget_tree,
}
with open("_data/adoption.json", "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2)
    f.write("\n")
print("Wrote _data/adoption.json — total %s (npm %s, NuGet %s), %d packages"
      % (out["total_display"], out["npm_display"], out["nuget_display"], out["packages"]))
