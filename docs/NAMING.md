# Product name

**Decision (owner, 2026-11-26): ViewPrism — Viewport Pass Exporter.** Extension id `viewprism`,
Python package `viewprism`, repository `ViewPrism`.

Collision check (web search only, 2026-11-26): no product named "ViewPrism" found. The closest are
Accusoft "Prizm Viewer" (document/image viewer) and other "…View…" XR/BIM viewers, all in different
categories. **Still to do before publishing:** J-PlatPat / USPTO / EUIPO search (classes 9 and 42).

### Trademark screening (web search only, 2026-11-26 — not legal clearance)

| Query | Result |
|---|---|
| "ViewPrism" trademark | No record for "ViewPrism". **Similar live US marks:** "PRISMVIEW" (Reg. 2159679,
registered 1990s, renewed; owner/goods not shown in the result) and "PRISM VIEW" (Reg. 3327821, Class 9,
medical imaging software, owner Prism Clinical Imaging, Inc.). Same words in reverse order. **Unresolved
concern**: whether this matters for an open-source Blender add-on needs a proper search, or advice from a
professional, before investing in the brand. |
| extensions.blender.org "viewprism" / "View Prism" | No such listing. A paid add-on "Prism Suite Beta"
(Superhive, UI theme) uses "Prism"; it is a different name. |
| "View Prism" software | Only unrelated "Prism …" products (accounting, compliance, property software). |

Sources (2026-11-26): trademarks.justia.com (PRISM VIEW 78899494, PRISMVIEW 75192479), markinton.com,
extensions.blender.org search results, superhivemarket.com (Prism Suite Beta). The official databases
(USPTO Trademark Search, EUIPO eSearch, WIPO Global Brand Database, J-PlatPat) were not queried: they
need interactive sessions. The extension id `viewprism` was not found on extensions.blender.org; it is
reserved only when an extension is uploaded.

The proposals below were prepared before the decision and are kept for the record.

## Name proposals (2026-11-26, before the decision)

Status: **proposal for the owner's decision**. Web search only. This is not a legal clearance.
J-PlatPat, USPTO, EUIPO and WIPO were not searched. Do that for the chosen name before publishing.
Rules that apply: the Blender Extensions ToS forbids "Blender" in the extension name. The extension
`id` must be lowercase letters, digits and underscores.

## What the name should carry

- the capture source: the **view / viewport / frame** you are looking at
- the output: **passes / data maps** (depth, normal, ID, mask)
- one-click speed, with no camera and no setup
- searchability on extensions.blender.org ("viewport", "depth", "pass", "export")

## Candidates

| # | Name (id) | Idea | Collision check (web search) | Notes |
|---|---|---|---|---|
| 1 | **ViewPass** (`viewpass`) | view → passes; current working name | No 3D/graphics product found. GitHub has unrelated "viewpass" repos (password-field Chrome extension, Django token pages); "VPass" is visitor-management software | Already used throughout the code. Downside: "pass" often reads as "password" in software search results |
| 2 | **FrameTap** (`frametap`) | "tap" the current frame to get its data | No product found (the search only returned other "Frame…" apps such as Dragonframe Tether and FrameUp) | Pass/password-free, short, brandable. Doesn't say "passes", so it needs the descriptive subtitle |
| 3 | **ViewGrab** (`viewgrab`) | grab the view as data | No product named ViewGrab found. Similar: a 2010 3ds Max script "view grabber" ([scriptspot](https://scriptspot.com/3ds-max/scripts/view-grabber)), Unigine AppGrabber | Clear meaning; "grab" is informal; small overlap with an old 3ds Max script |
| 4 | **PassFrame** (`passframe`) | the passes of one frame | No product found | Neutral; still contains "Pass" |
| 5 | **ViewTap** (`viewtap`) | like FrameTap, view-centric | No product found (only "ViewerApp", "iViewer") | Very short; meaning is less obvious |
| 6 | **NoCam Passes** (`nocam_passes`) | states the main advantage | No product found (camera add-ons such as EasyCam, PocketCam, Cam Tools exist) | Communicates the USP but sounds negative, and camera view is also supported |
| — | **Viewport Pass Exporter** | fully descriptive | Searches show the phrase "viewport passes" only in Blender development discussions, not as a product | Best for platform search; weak as a brand. Recommended as the **tagline/subtitle** for any choice |

Avoid (existing names in software/graphics): **SnapPass** (Pinterest password sharing; iOS image
editor), **PassGrab** (GitHub password stealers), **PassView** (well-known Windows password-recovery
utilities use this name), **PassKit** (Apple), **ClearPass** (network access control), **Vantage**
(Chaos renderer), **Depthkit** (volumetric capture), **Glimpse** (image editor fork).

## Recommendation

1. **Keep "ViewPass"** with the descriptive subtitle **"Viewport Pass Exporter"**. This keeps continuity,
   needs no code rename, and has no 3D-space collision found. The password connotation is mitigated by
   the subtitle and by the extension's tags.
2. If you prefer a name with no "pass/password" ambiguity: **FrameTap**.

Before publishing either: check J-PlatPat / USPTO / EUIPO (classes 9 and 42), confirm the `id` is free on
extensions.blender.org, and then rename the repository (GitHub keeps redirects from the old name).

Search sources used for the candidates above (2026-11-26): web searches for each candidate name; the
earlier competitor research in [`research/competitors_raw_2026-11-26.md`](research/competitors_raw_2026-11-26.md)
(section 5) covers ViewPass, PassSnap, SnapPass, PassGrab, ViewportPasses, DepthNormal, ViewSnap,
ViewGrab, DepthSnap and PassCam.
