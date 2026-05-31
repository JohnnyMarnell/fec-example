#!/usr/bin/env python3
"""Analyze FEC contribution data: aggregate and visualize a company's political donations."""
import re
from pathlib import Path

import click
import duckdb
import matplotlib.pyplot as plt
import pandas as pd


@click.command()
@click.argument("csv_path", default="./csv/TractorSupplyFECr.csv", required=False)
def analyze(csv_path):
    """Aggregate and visualize FEC contributions from CSV_PATH.

    CSV_PATH defaults to ./csv/TractorSupplyFECr.csv.
    Expects AllPacs.xslx.csv and Aristotle1.xlsx.csv in ./csv/.
    """
    company_name = re.sub(r"FECr?$", "", Path(csv_path).stem, flags=re.IGNORECASE).upper()

    fec = pd.read_csv(csv_path)
    allpacs = pd.read_csv("./csv/AllPacs.xslx.csv")
    aristotle = pd.read_csv("./csv/Aristotle1.xlsx.csv")

    con = duckdb.connect(":memory:")

    click.echo(f"Analyzing: {company_name}")
    click.echo(f"Input file: {csv_path}")
    click.echo(f"Rows loaded: {len(fec):,}\n")

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

    saspac3['zipcc'] = saspac3['zip_raw'].str[:5]
    saspac3['compervar'] = saspac3['company'] + ' - ' + saspac3['last'] + ' - ' + saspac3['zipcc']

    ruler = "\n" + "=" * 70

    # Step 2: Transaction-level stats
    click.echo("\nContributions by Company (Transaction-Level)" + ruler)

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
    click.echo(f"Count:              {stat('count'):,}")
    click.echo(f"Max:                ${stat('max_amount'):,.2f}")
    click.echo(f"Mean:               ${stat('mean_amount'):,.2f}")
    click.echo(f"Total:              ${total:,.2f}")
    click.echo(f"Democrat %:         {100 * stat('dem_amount') / total:.2f}%")
    click.echo(f"Republican %:       {100 * stat('rep_amount') / total:.2f}%")
    click.echo(f"Other %:            {100 * stat('other_amount') / total:.2f}%")

    # Step 3: Aggregate by person and apply 60% rule
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
    click.echo("\nContributors by Company (60% Rule, Person-Level)" + ruler)

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

    click.echo(f"Unique Contributors: {total_people:,}")
    click.echo(f"Total Amount:        ${total_dollars:,.2f}")
    click.echo("\nParty Breakdown (60% rule):")

    for _, row in contrib_stats.iterrows():
        party_name = {'D': 'Democrat', 'R': 'Republican', 'N': 'None/Other'}.get(row['pCode'], row['pCode'])
        click.echo(f"  {party_name:20s} {row['people_count']:4.0f} people ({row['pct']:5.2f}%)")

    # Step 5: Top committees
    click.echo("\nTop 10 Recipient Committees " + ruler)

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
        click.echo(f"{row['committee_name'][:50]:50s} [{row['party']}] ${row['total_amount']:>10,.2f} ({row['count']:3.0f} txns)")

    click.echo("\n" + "=" * 70)
    click.echo("SUMMARY")
    click.echo("=" * 70)
    click.echo(f"Company:                {company_name}")
    click.echo(f"Total transactions:     {len(saspac3):,}")
    click.echo(f"Total amount:           ${saspac3['amount'].sum():,.2f}")
    click.echo(f"Unique contributors:    {total_people}")
    click.echo(f"Avg txns per person:    {len(saspac3) / total_people:.1f}")
    click.echo("=" * 70)

    _show_charts(company_name, contrib_stats)


def _show_charts(company_name, contrib_stats):
    """Pie charts: party breakdown by contributor count and dollar amount."""
    color_map = {'D': '#3498db', 'R': '#e74c3c', 'N': '#95a5a6', 'I': '#f39c12', 'L': '#9b59b6', 'G': '#27ae60'}
    party_full = {
        'D': 'Democrat', 'R': 'Republican', 'N': 'None/Other',
        'I': 'Independent', 'L': 'Libertarian', 'G': 'Green',
    }

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle(f'{company_name} — Political Contributions (60% Rule)', fontsize=14, fontweight='bold')

    count_labels, counts, count_colors = [], [], []
    dollar_labels, dollars, dollar_colors = [], [], []
    for _, row in contrib_stats.iterrows():
        name = party_full.get(row['pCode'], row['pCode'])
        c = color_map.get(row['pCode'], '#95a5a6')
        count_labels.append(f"{name}\n{row['people_count']:.0f} people")
        counts.append(row['people_count'])
        count_colors.append(c)
        dollar_labels.append(f"{name}\n${row['party_dollars']:,.0f}")
        dollars.append(row['party_dollars'])
        dollar_colors.append(c)

    ax1.pie(counts, labels=count_labels, colors=count_colors, autopct='%1.1f%%', startangle=90)
    ax1.set_title('Contributors by Party')
    ax2.pie(dollars, labels=dollar_labels, colors=dollar_colors, autopct='%1.1f%%', startangle=90)
    ax2.set_title('Dollar Amounts by Party')

    plt.tight_layout()
    click.echo("\nOpening chart window...")
    plt.show()


if __name__ == "__main__":
    analyze()
