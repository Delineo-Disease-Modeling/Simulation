PY := python
SCRIPTS := scripts

.PHONY: data prepare sim compare all clean

# 1) Fetch reliable public data (JHU Global for a country)
data:
	$(PY) $(SCRIPTS)/fetch_data.py --country US

# 2) Prepare processed series (daily or weekly)
prepare:
	$(PY) $(SCRIPTS)/prepare_data.py --agg weekly

# 3) Run simulator via HTTP (assumes docker compose up or python app.py already running)
sim:
	$(PY) $(SCRIPTS)/run_simulation.py --length 80640 --location barnsdall --step_minutes 60

# 4) Compare and produce report
compare:
	$(PY) $(SCRIPTS)/compare.py --agg weekly

all: data prepare sim compare

clean:
	rm -f reports/*.png reports/*.csv artifacts/*.json artifacts/*.csv
