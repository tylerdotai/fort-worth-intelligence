# Parcel / Appraisal / Tax Layer

## Why this layer matters

This is one of the highest-value civic intelligence layers in Fort Worth.

It is the layer that answers:
- what parcel is this?
- what is it worth?
- which tax bodies apply?
- where do ownership and record references live?
- what public entities materially affect this property?

## Core sources

### Tarrant Appraisal District (TAD)
- Canonical source: `https://www.tad.org`
- Role: appraisal district system of record for valuation and parcel-level tax appraisal context
- Type: portal / docs / potentially GIS-adjacent references
- Priority: highest

### Tarrant County Tax Assessor-Collector
- Canonical source: `https://taxoffice.tarrantcountytx.gov` (DAO lead included `tarranttax.com`)
- Role: tax collection, payments, deadlines, office procedures
- Type: portal / docs
- Priority: highest

### Tarrant County public records search
- Canonical source: `https://tarrant.tx.publicsearch.us`
- Role: records context for deeds / filings / searchable public information
- Type: public records portal
- Priority: high

### Fort Worth map portal
- Canonical source: `https://mapit.fortworthtexas.gov`
- Role: address-centric map surface and geospatial overlays
- Type: GIS / map portal
- Priority: highest

## What this layer should eventually resolve

For a single address or parcel, the system should return:
- parcel / account reference
- appraisal district reference
- tax office reference
- city / county / school district overlaps
- utility / special district overlaps
- council and representation layers
- map layer context

## Product implication

This layer is the backbone of:
- address-to-government resolver
- real estate diligence tool
- homeowner tax / governance explainer
- parcel-centric development intelligence
