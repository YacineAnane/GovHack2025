# GovHack 2025: Visualising Victoria’s near-term change

**Tagline:** See what’s being built, where people move, and what that means for schools, safety and everyday access, then ask questions about it.

---

## The problem (plain)
Cities change fast. A single new development can shift school demand, parking, or safety in ways that aren’t obvious until it’s too late. Planners, community groups and residents need simple, evidence-driven views of future development and local service pressure, not spreadsheets.

## What we built
A lightweight web app that brings together 2025 building permits, crime data, and school catchment / enrolment info into one interactive interface, with an AI assistant that answers questions *about the plots you’re looking at*.

Key pieces:
- Interactive map of **building permits (2025, Victoria)** showing location, type and estimated capacity.  
- Crime visualisations: map + distribution charts + simple breakdowns to spot trends by area.  
- School map with reported enrolments and capacity signals so you can see where demand is growing.  
- An integrated AI-powered helper: point at a plot or select charts and ask plain-English questions (e.g., “Which primary schools are likely to face capacity pressure within 1–2 km of these new developments?”). The assistant grounds answers in the visible plots and data.

---

## Why this matters for the GovHack challenges
- **20-Minute Neighbourhoods:** We surface how new developments change local access to services, identify gaps in schools, parks, or safety within walking distance. That gives communities and councils actionable starting points for targeting improvements.  
- **Community Housing & Infrastructure Planning:** By visualising where permits cluster and overlaying school capacity and crime trends, the app highlights neighbourhoods likely to experience housing stress or require upgraded services.

---

## Example uses (real, direct)
- A councillor checks a suburb and asks: “Will local primary schools need extra capacity if all these permits become houses?”  
- A community group filters for high-permit density + rising crime and exports a simple one-page brief to start a conversation with the council.  
- A planner compares permit types (mixed-use vs single dwellings) to anticipate transport or childcare needs.


## Usage:
install packages:
```
pip install -r requirements.txt
```
OR
```
conda env create -f environment.yml -n env_name
conda activate env_name
```

To use AI:
create a file named '.env' at the root of the project and write your open AI api key inside. Replace \<API_KEY\> with yours on the template bellow:
```
OPENAI_API_KEY=<API_KEY>
```