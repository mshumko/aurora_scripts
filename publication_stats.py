"""
Get an ADS API Token
1. Log in the NASA ADS/SciX interface.
2. Go to your Account Settings > API Token.
3. Copy your unique token string.
4. Save the key as a "ADS_API_TOKEN" variable in the secret_tokens.py file. 
"""

import datetime
import time
import pandas as pd
import requests

import matplotlib.pyplot as plt

import secret_tokens

# Replace with your actual NASA ADS API token
ADS_TOKEN = secret_tokens.ADS_API_TOKEN
headers = {"Authorization": f"Bearer {ADS_TOKEN}"}
url = "https://api.adsabs.harvard.edu/v1/search/query"

# Define your abstract keyword query
# Use boolean operators to target magnetospheric physics specifically
keywords = [
    'magnetosphere', 
    'magnetospheric', 
    'geomagnetic storm', 
    'substorm', 
    'aurora', 
    'magnetotail', 
    'radiation belt',
    'reconnection',
    'ionosphere',
]
keywords_query = " ".join([f'abs:"{keyword}" OR' for keyword in keywords]).rstrip(" OR")

# Define the timeframe (past few years)
start_year = 1975
end_year = 2025

monthly_data = []

annual_data = []
for year in range(start_year, end_year + 1):
    query_params = {"q": f'{keywords_query} year:"{year}"', "rows": 0}
    response = requests.get(url, params=query_params, headers=headers)
    num_found = response.json().get("response", {}).get("numFound", 0)
    annual_data.append({"Year": year, "Count": num_found})

    # Polite back-off to respect API rate limits
    time.sleep(0.5)

# Convert to a DataFrame and parse dates
df = pd.DataFrame(annual_data)
df["Year"] = pd.to_datetime(df["Year"], format="%Y")
df.set_index("Year", inplace=True)

# Save or inspect your time series
df.to_csv("magnetosphere_pub_trends.csv")
print("\nCalculation complete! Data saved to magnetosphere_pub_trends.csv.")

fig, ax = plt.subplots(figsize=(8, 6))
plt.tick_params(axis='both', labelsize=15)
ax.plot(df.index, df["Count"]/1000, marker='o', c='k')
ax.set_xlabel("Year", fontsize=20)
ax.set_ylabel("Number of Publications/1000", fontsize=20)
ax.set_title("Magnetosphere Publication Trends", fontsize=20)
ax.grid(True)
ax.text(
    0.03, 
    0.97, 
    f"Source: NASA ADS\n\nKeywords:\n{'\n'.join(keywords)}",
    transform=ax.transAxes, 
    verticalalignment='top',
    fontsize=15,
    bbox=dict(facecolor='white', alpha=0.8, edgecolor='purple', boxstyle='round,pad=0.5')
    )
plt.tight_layout()
plt.show()
pass