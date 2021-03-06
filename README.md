# bid-ask-visualization

This repository contains methods for retrieving bid ask data and methods for analyzing and visualizing this data. The streamlit app that visualizes this data gives context and motivation for this project.

Description of files:

* **requirements.txt**: contains python packages used to run these scripts
* **environment.yml**: contains instructions to install an anaconda environment with the specified packages
* **etf.csv**: contains information about ETFs used to both retrieve, analyze and visualize data
* **get_quotes_alpaca_polygon.py**: script to retrieve data from polygon.io and alpaca APIs
* **analyze_data.py**: file containing methods to process retrieved data into a form that is easier to process and visualize
* **app.py**: steamlit visualization script
* **test_averages.py**: method meant to test that the averages of data obtained from polygon.io are accurate.
* data/**2021-02-03_ESGV.csv**: contains bid-ask spread data used in the first plot in app.py
* data/**quoted_spread.pkl**: contains quoted spreads used in the results section in app.py


