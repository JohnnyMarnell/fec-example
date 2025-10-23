#!/usr/bin/env python3
"""
Minimal FEC Analysis Script
Reproduces Companies.htm statistics using pandas + DuckDB
Usage: python main.py [path/to/CompanyFECr.csv]
"""
import pandas as pd
import duckdb
import sys
import re
from pathlib import Path
import matplotlib.pyplot as plt

# Get CSV file path from args or use default
if len(sys.argv) > 1:
    fec_csv_path = sys.argv[1]
else:
    fec_csv_path = 'TractorSupplyFECr.csv'
company_name = re.sub(r'FECr?$', '', Path(fec_csv_path).stem, flags=re.IGNORECASE).upper()

# Load data
fec = pd.read_csv(fec_csv_path)
allpacs = pd.read_csv('AllPacs.xslx.csv')
aristotle = pd.read_csv('Aristotle1.xlsx.csv')

# Initialize DuckDB
con = duckdb.connect(':memory:')

print(f"Analyzing: {company_name}")
print(f"Input file: {fec_csv_path}")
print(f"Rows loaded: {len(fec):,}\n")

# Step 1: Join with party lookups & clean data
saspac3 = con.execute(f"""
    SELECT
        f.*,
        COALESCE(a."Political Affiliation", ar.Party, 'N') as party,
        '{company_name}' as company,
        UPPER(TRIM(contributor_last_name)) as last,
        REGEXP_REPLACE(CAST(contributor_zip AS VARCHAR), '[^0-9]', '', 'g') as zip_raw,
        contribution_receipt_amount as amount
    FROM fec f
    LEFT JOIN allpacs a ON f.committee_id = a.committee_id
    LEFT JOIN aristotle ar ON f.committee_id = ar.Code
""").df()

# Clean zip to 5 digits
saspac3['zipcc'] = saspac3['zip_raw'].str[:5]

# Create person ID: company - lastname - zip
saspac3['compervar'] = saspac3['company'] + ' - ' + saspac3['last'] + ' - ' + saspac3['zipcc']

# Step 2: Transaction-level stats
ruler = "\n" + "=" * 70
print("\nContributions by Company (Transaction-Level)" + ruler)

trans_stats = con.execute("""
    SELECT
        COUNT(*) as count,
        MAX(amount) as max_amount,
        AVG(amount) as mean_amount,
        SUM(amount) as total_amount,
        SUM(CASE WHEN party = 'D' THEN amount ELSE 0 END) as dem_amount,
        SUM(CASE WHEN party = 'R' THEN amount ELSE 0 END) as rep_amount,
        SUM(CASE WHEN party NOT IN ('D', 'R') THEN amount ELSE 0 END) as other_amount
    FROM saspac3
""").df()

stat = lambda key: trans_stats[key].iloc[0]
total = stat('total_amount')
print(f"Count:              {stat('count'):,}")
print(f"Max:                ${stat('max_amount'):,.2f}")
print(f"Mean:               ${stat('mean_amount'):,.2f}")
print(f"Total:              ${total:,.2f}")
print(f"Democrat %:         {100 * stat('dem_amount') / total:.2f}%")
print(f"Republican %:       {100 * stat('rep_amount') / total:.2f}%")
print(f"Other %:            {100 * stat('other_amount') / total:.2f}%")

# Step 3: Aggregate by person and apply 60% rule (CTE approach)
person_totals = con.execute("""
    WITH person_sums AS (
        SELECT
            compervar,
            SUM(CASE WHEN party = 'D' THEN amount ELSE 0 END) as Dsum,
            SUM(CASE WHEN party = 'R' THEN amount ELSE 0 END) as Rsum,
            SUM(CASE WHEN party = 'I' THEN amount ELSE 0 END) as Isum,
            SUM(CASE WHEN party = 'L' THEN amount ELSE 0 END) as Lsum,
            SUM(CASE WHEN party = 'G' THEN amount ELSE 0 END) as Gsum,
            SUM(amount) as total
        FROM saspac3
        GROUP BY compervar
    )
    SELECT
        compervar,
        Dsum, Rsum, Isum, Lsum, Gsum,
        total,
        CASE
            WHEN total = 0 THEN 'N'
            WHEN Dsum / total >= 0.60 THEN 'D'
            WHEN Rsum / total >= 0.60 THEN 'R'
            WHEN Isum / total >= 0.60 THEN 'I'
            WHEN Lsum / total >= 0.60 THEN 'L'
            WHEN Gsum / total >= 0.60 THEN 'G'
            ELSE 'N'
        END as pCode
    FROM person_sums
""").df()

# Step 4: Contributor-level stats
print("\nContributors by Company (60% Rule, Person-Level)" + ruler)

contrib_stats = con.execute("""
    SELECT
        pCode,
        COUNT(*) as people_count,
        SUM(total) as party_dollars,
        100.0 * COUNT(*) / SUM(COUNT(*)) OVER () as pct,
        SUM(COUNT(*)) OVER () as total_people,
        SUM(SUM(total)) OVER () as total_dollars
    FROM person_totals
    GROUP BY pCode
    ORDER BY people_count DESC
""").df()

total_people = int(contrib_stats['total_people'].iloc[0])
total_dollars = contrib_stats['total_dollars'].iloc[0]

print(f"Unique Contributors: {total_people:,}")
print(f"Total Amount:        ${total_dollars:,.2f}")
print(f"\nParty Breakdown (60% rule):")

for _, row in contrib_stats.iterrows():
    party_name = {'D': 'Democrat', 'R': 'Republican', 'N': 'None/Other'}.get(row['pCode'], row['pCode'])
    print(f"  {party_name:20s} {row['people_count']:4.0f} people ({row['pct']:5.2f}%)")

# Step 5: Top committees
print("\nTop 10 Recipient Committees " + ruler)

top_committees = con.execute("""
    SELECT
        committee_name,
        party,
        COUNT(*) as count,
        MAX(amount) as max_amount,
        AVG(amount) as mean_amount,
        SUM(amount) as total_amount
    FROM saspac3
    GROUP BY committee_name, party
    ORDER BY total_amount DESC
    LIMIT 10
""").df()

for _, row in top_committees.iterrows():
    print(f"{row['committee_name'][:50]:50s} [{row['party']}] ${row['total_amount']:>10,.2f} ({row['count']:3.0f} txns)")

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"Company:                {company_name}")
print(f"Total transactions:     {len(saspac3):,}")
print(f"Total amount:           ${saspac3['amount'].sum():,.2f}")
print(f"Unique contributors:    {total_people}")
print(f"Avg txns per person:    {len(saspac3) / total_people:.1f}")
print("=" * 70)


def show_party_breakdown_chart(company_name, contrib_stats):
    """Display pie charts showing party breakdown by contributors and dollars."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle(f'{company_name} - Political Contributions Analysis (60% Rule)', fontsize=14, fontweight='bold')

    # Chart 1: Contributors by party
    party_labels = []
    party_counts = []
    party_colors = []
    color_map = {'D': '#3498db', 'R': '#e74c3c', 'N': '#95a5a6', 'I': '#f39c12', 'L': '#9b59b6', 'G': '#27ae60'}

    for _, row in contrib_stats.iterrows():
        party_name = {'D': 'Democrat', 'R': 'Republican', 'N': 'None/Other', 'I': 'Independent', 'L': 'Libertarian', 'G': 'Green'}.get(row['pCode'], row['pCode'])
        party_labels.append(f"{party_name}\n{row['people_count']:.0f} people")
        party_counts.append(row['people_count'])
        party_colors.append(color_map.get(row['pCode'], '#95a5a6'))

    ax1.pie(party_counts, labels=party_labels, colors=party_colors, autopct='%1.1f%%', startangle=90)
    ax1.set_title('Contributors by Party')

    # Chart 2: Dollar amounts by party
    dollar_labels = []
    dollar_amounts = []
    dollar_colors = []

    for _, row in contrib_stats.iterrows():
        party_name = {'D': 'Democrat', 'R': 'Republican', 'N': 'None/Other', 'I': 'Independent', 'L': 'Libertarian', 'G': 'Green'}.get(row['pCode'], row['pCode'])
        dollar_labels.append(f"{party_name}\n${row['party_dollars']:,.0f}")
        dollar_amounts.append(row['party_dollars'])
        dollar_colors.append(color_map.get(row['pCode'], '#95a5a6'))

    ax2.pie(dollar_amounts, labels=dollar_labels, colors=dollar_colors, autopct='%1.1f%%', startangle=90)
    ax2.set_title('Dollar Amounts by Party')

    plt.tight_layout()
    print(f"\n📊 Opening chart window...")
    plt.show()


# Display visualization
show_party_breakdown_chart(company_name, contrib_stats)
