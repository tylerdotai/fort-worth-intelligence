<a id="readme-top"></a>

<br />
<div align="center">
  <img src="assets/fort-worth-intelligence.png" alt="Fort Worth Intelligence" width="180">

  <h3 align="center">Fort Worth Intelligence</h3>

  <p align="center">
    Structured source catalog and research narrative for the deepest validated public data surface around Fort Worth and Tarrant County.
    <br />
    <a href="docs/source-catalog.md"><strong>Explore the source catalog »</strong></a>
    <br />
    <br />
    <a href="docs/research-narrative.md">Research Narrative</a>
    ·
    <a href="https://github.com/tylerdotai/fort-worth-intelligence/issues">Report Bug</a>
    ·
    <a href="https://github.com/tylerdotai/fort-worth-intelligence/issues">Request Feature</a>
  </p>
</div>

---

[![MIT License][license-shield]][license-url]
[![Issues][issues-shield]][issues-url]
[![Stars][stars-shield]][stars-url]
[![Forks][forks-shield]][forks-url]

## About The Project

Most “city data” projects are thin wrappers around a city homepage or open data portal.

Fort Worth does not work like that.

The real public-information surface is distributed across:
- City of Fort Worth
- Tarrant County
- Legistar and vendor-hosted records systems
- appraisal and tax systems
- school districts
- transit and regional planning bodies
- water and special districts
- health systems
- airport and regional infrastructure surfaces
- federal and state APIs that enrich the local picture

This repo exists to map that whole surface in a way that is actually usable.

It combines:
- a **structured source catalog**
- a **research narrative** explaining the landscape
- DAO-discovered discovery maps used as leads only
- validation bias toward official and institutional sources

### Built With

- Markdown
- Python-friendly raw source files
- GitHub
- Official public APIs and public portals

## Repository Structure

```text
fort-worth-intelligence/
├── assets/
│   └── fort-worth-intelligence.png
├── data/
│   └── raw/
│       └── discovery_urls.txt
├── docs/
│   ├── source-catalog.md
│   └── research-narrative.md
└── scripts/
```

## What’s Included

### 1. Structured Source Catalog
`docs/source-catalog.md`

A normalized catalog of Fort Worth / Tarrant public data sources, organized by domain:
- core government
- council / agendas / ordinances
- elections / representation
- property / appraisal / tax / parcel
- zoning / planning / development
- crime / courts / public safety
- schools / ISDs / colleges
- transit / roads / infrastructure / GIS
- utilities / water / special districts / health
- business / nonprofits / economic development

Each source is tagged with:
- validation tier
- access type
- role in the data graph
- notes for downstream productization

### 2. Research Narrative
`docs/research-narrative.md`

A strategic narrative explaining:
- why the DAO source map matters
- what shape the Fort Worth civic graph actually takes
- where the highest-value data layers are
- what product and infrastructure opportunities this unlocks
- what to build next if the goal is a serious Fort Worth intelligence stack

### 3. Discovery Map Input
`data/raw/discovery_urls.txt`

The DAO source list extracted from `FWTX-DAO/fwtx-scraper` and preserved as a discovery input.

Important: this list is treated as **lead generation**, not truth.

## Methodology

This repo follows a strict validation rule:

1. **Use DAO repos as discovery maps**
2. **Independently verify each source**
3. **Prefer official domains and official APIs**
4. **Classify each source by access type and reliability**
5. **Document what can be operationalized into real intelligence products**

### Validation Tiers

- **Tier A**: official government / institutional / direct API / direct system of record
- **Tier B**: official vendor-hosted public system acting as record surface
- **Tier C**: secondary or derivative source, only used when necessary

## Why This Matters

The highest-value civic product here is probably not a “wiki.”

It is an **address-centric intelligence layer**.

If you can resolve:
- parcel
- tax bodies
- school district
- city / county districts
- utilities / special districts
- transit context
- nearby legislative actions
- zoning and development surfaces

for a single Fort Worth address, you have something immediately useful for:
- residents
- journalists
- developers
- real-estate operators
- civic orgs
- local researchers
- policy and campaign teams

## Roadmap

- [x] Build initial Fort Worth / Tarrant source catalog
- [x] Write research narrative from validated sources
- [x] Preserve DAO-discovered source inventory
- [ ] Normalize all 83 DAO sources into canonical institution records
- [ ] Validate every source against official domains
- [ ] Add API / portal / GIS / docs / scrape capability matrix
- [ ] Add address-centric source resolution layer
- [ ] Add district / parcel / school / tax relationship model
- [ ] Add legislative / agenda / ordinance change-tracking targets
- [ ] Add machine-readable JSON source registry

## Contributing

Contributions should improve one of three things:
- source validation
- source coverage
- structure and usability of the intelligence model

If you contribute:
1. prefer official sources
2. include exact URLs
3. note whether access is API, portal, GIS, bulk, docs, or scrape-only
4. document validation confidence
5. avoid mixing speculation with confirmed information

## License

Distributed under the MIT License. See `LICENSE` for more information.

## Acknowledgments

- [FWTX-DAO/fwtx-wiki-engine](https://github.com/FWTX-DAO/fwtx-wiki-engine)
- [FWTX-DAO/fwtx-scraper](https://github.com/FWTX-DAO/fwtx-scraper)
- [Best-README-Template](https://github.com/othneildrew/Best-README-Template)
- official Fort Worth, Tarrant County, district, regional, and federal public data sources

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- MARKDOWN LINKS & IMAGES -->
[license-shield]: https://img.shields.io/github/license/tylerdotai/fort-worth-intelligence.svg?style=for-the-badge
[license-url]: https://github.com/tylerdotai/fort-worth-intelligence/blob/main/LICENSE
[issues-shield]: https://img.shields.io/github/issues/tylerdotai/fort-worth-intelligence.svg?style=for-the-badge
[issues-url]: https://github.com/tylerdotai/fort-worth-intelligence/issues
[stars-shield]: https://img.shields.io/github/stars/tylerdotai/fort-worth-intelligence.svg?style=for-the-badge
[stars-url]: https://github.com/tylerdotai/fort-worth-intelligence/stargazers
[forks-shield]: https://img.shields.io/github/forks/tylerdotai/fort-worth-intelligence.svg?style=for-the-badge
[forks-url]: https://github.com/tylerdotai/fort-worth-intelligence/network/members
