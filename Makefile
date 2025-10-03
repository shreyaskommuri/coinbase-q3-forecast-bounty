.PHONY: venv install test sentiment q1 q2 q3 backtest forecast

venv:
	python3 -m venv venv

install: venv
	. venv/bin/activate && pip install -r requirements.txt

test:
	. venv/bin/activate && pytest

q1:
	. venv/bin/activate && python scripts/subscriptions_model.py --config configs/q1_2025.json

q2:
	. venv/bin/activate && python scripts/subscriptions_model.py --config configs/q2_2025.json

q3:
	. venv/bin/activate && python scripts/subscriptions_model.py --config configs/q3_2025.json

backtest:
	. venv/bin/activate && python scripts/backtest_q2.py

forecast:
	. venv/bin/activate && python scripts/q3_forecast.py

sentiment:
	. venv/bin/activate && python scripts/build_sentiment_factor.py --start 2025-07-01 --end 2025-09-30

all: install test q1 q2 q3 backtest forecast sentiment
