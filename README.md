# Sleevecast status

The public status page at https://status.sleevecast.com. A scheduled GitHub Action (`check.yml`) runs `check.py`
every 5 minutes against Sleevecast's public endpoints and commits `data.json` when a state changes or a new hour
begins; GitHub Pages serves `index.html`, which reads it. It lives here, not on Sleevecast's servers, so it stays
up when they are down.
