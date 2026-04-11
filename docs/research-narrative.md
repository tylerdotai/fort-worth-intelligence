# Fort Worth Intelligence Research Narrative

## Why this repo exists

The goal is not to make another civic bookmark list.

The goal is to assemble the deepest practical intelligence surface possible for **Fort Worth + Tarrant County**, using:
- official public data APIs
- official institutional websites
- searchable vendor-hosted public systems
- geospatial layers
- records portals
- civic documents
- and DAO-discovered source maps as discovery aids only

This repo treats the FWTX DAO repos as useful leads, then independently validates the real public data surface.

---

## What the DAO got right

The DAO pointed at something much larger than a city wiki.

They identified a regional public-information mesh spanning:
- city government
- county government
- schools and colleges
- transit
- water districts
- emergency services districts
- airports
- tax and appraisal systems
- special-purpose districts
- records portals

That is the correct mental model.

Most civic tools fail because they pretend “the city” is one website.

It isn’t.

Fort Worth is really a stack of overlapping institutions, boundaries, and systems of record.

If you want a usable intelligence layer, you have to map the stack.

---

## The actual shape of the problem

A Fort Worth resident, investor, journalist, or builder does not need “city information.”
They need answers to composite questions like:

- what public bodies govern this address?
- which council district, ISD, tax body, and utility district apply here?
- which meetings next week affect this neighborhood?
- what zoning or ordinance actions are coming up?
- where do I pull official parcel, tax, and district info?
- what county systems and city systems overlap on this issue?

That means the repo should think in terms of **entity resolution and relationship mapping**, not just crawling pages.

---

## Core insight

The highest-value Fort Worth data product is probably **address-centric**.

Most people do not think in ontology terms.
They think in:
- address
- parcel
- neighborhood
- district
- school zone
- permit
- property tax
- transit access
- upcoming meeting impact

So the long-term shape of this work should likely be:

**address in → full civic context out**

That requires combining:
- GIS layers
- parcel / appraisal / tax systems
- district boundaries
- representative mapping
- school district mapping
- utility / MUD / special district overlays
- transportation overlays
- legislative and planning intelligence

That is much more valuable than a static report.

---

## Data surface by strategic value

## 1. Property + GIS + Tax + District Boundaries

This is probably the most commercially useful layer.

Why:
- homebuyers care
- developers care
- real estate investors care
- journalists care
- relocation families care
- city nerds care

If you can resolve:
- parcel
- valuation
- tax body
- city district
- county district
- ISD
- utility district
- flood / infrastructure layers

for one address, you have an immediately useful product.

## 2. Legislative / Agenda / Ordinance Tracking

The Legistar surface is one of the most important official sources in the stack.

Why:
- this is where city decisions become visible
- it creates change intelligence, not just reference info
- it can connect agenda items to geography, departments, and projects

That means the intelligence product should not just mirror agendas.
It should answer:
- what changed?
- who owns this issue?
- what department is involved?
- which neighborhood or district is affected?

## 3. School District Governance

The DAO was smart to include ISDs.

Families and property owners care about school districts as much as city government, sometimes more.

District governance data creates strong use cases around:
- relocation
- tax and bond awareness
- school board politics
- district comparison
- family decision support

## 4. Special District / Utility Complexity

This is where local governance gets weird and expensive.

People usually do not know:
- whether they are inside a MUD
- what water district serves them
- what emergency services district covers them
- which regional authority affects them

If this repo gets good at mapping those layers, it becomes genuinely differentiated.

---

## What a serious Fort Worth intelligence stack should contain

### Source registry
A canonical source registry with:
- institution name
- canonical domain
- source type
- access type
- validation status
- notes about structure and update cadence

### Entity model
Canonical entities for:
- institution
- district
- official
- address
- parcel
- meeting
- agenda item
- project
- ordinance
- utility / special district
- school district
- transit body

### Change tracking
Static data is useful.
Changed data is where the real value starts.

Track changes on:
- agendas
- ordinances
- department pages
- district maps
- public notices
- bond / election pages
- project pages

### GIS layer normalization
Especially important for:
- council districts
- school districts
- parcel overlays
- utility districts
- flood / mobility / infrastructure surfaces

### Address resolver
This is the wedge.

If this gets built well, it can unify everything else.

---

## What product directions this supports

### 1. Fort Worth Civic Intelligence Search
A search layer across all validated institutions.

### 2. Address-to-Government Resolver
Best practical wedge.

### 3. Municipal Watchtower
Agenda, ordinance, and notice change detection.

### 4. Development / Real Estate Due Diligence Tool
Property + district + zoning + tax + utility + meeting intelligence.

### 5. API Layer for Fort Worth Builders
Turn the source registry + normalized entities into an API.

That is probably the most durable moat.

---

## What we should do next

### Phase 1 — validated source inventory
- normalize the 83-source DAO list
- confirm official domains
- classify by access type
- identify APIs and machine-readable endpoints

### Phase 2 — high-value civic layers
- parcel / appraisal / tax
- GIS and district boundaries
- council / Legistar / ordinance intelligence
- school district governance
- transit / infrastructure

### Phase 3 — address-first model
- address resolver
- district and institution overlays
- representative mapping
- school / utility / tax body relationships

### Phase 4 — change intelligence
- monitor agendas and notices
- detect content and data changes
- issue alerts or build analyst workflow

---

## Bottom line

The DAO repos were useful because they reveal the shape of the local data graph.
But the actual value comes from validating, structuring, and operationalizing those sources ourselves.

The best framing for this repo is not “Fort Worth wiki.”
It is:

**Fort Worth civic intelligence infrastructure**

That’s the direction with the most leverage.
