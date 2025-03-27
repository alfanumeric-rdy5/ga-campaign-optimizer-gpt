
import streamlit as st
import pandas as pd
import openai

# Load OpenAI API key
openai.api_key = st.secrets["OPENAI_API_KEY"]

st.title("Campaign Optimizer GPT v5")

with st.expander("📘 How to Use This App"):
    st.markdown("""
Upload two CSVs exported from Google Ads (e.g., last month vs. this month).  
Required columns:
- **Campaign**
- **Ad Group**
- **CPA**
- **CTR**
- **Cost**
- **Conversions**
- **Impressions**
- *(Optional)* **Keyword**
    """)

st.subheader("Upload Two CSV Files for Comparison")
current_file = st.file_uploader("Current Period CSV", type="csv", key="current")
previous_file = st.file_uploader("Previous Period CSV", type="csv", key="previous")

st.subheader("Campaign Goals")
target_cpa = st.number_input("Target CPA ($)", min_value=0.0, step=0.1)
target_ctr = st.number_input("Target CTR (%)", min_value=0.0, step=0.1)

st.subheader("Alert Sensitivity")
cpa_threshold = st.slider("Flag CPA changes over (%)", 5, 100, 15)
ctr_threshold = st.slider("Flag CTR changes over (%)", 5, 100, 15)

st.subheader("Add Custom Notes (Optional)")
custom_context = st.text_area("e.g. New landing page, Black Friday, etc.")

level = st.selectbox("Compare performance by:", ["Ad Group", "Campaign"])

def calculate_changes(curr_df, prev_df, level_col):
    merged = pd.merge(curr_df, prev_df, on=level_col, suffixes=("_curr", "_prev"))
    alerts, movers = [], []

    for _, row in merged.iterrows():
        try:
            cpa_change = ((row["CPA_curr"] - row["CPA_prev"]) / row["CPA_prev"]) * 100 if row["CPA_prev"] else 0
            ctr_change = ((row["CTR_curr"] - row["CTR_prev"]) / row["CTR_prev"]) * 100 if row["CTR_prev"] else 0
            spend_change = ((row["Cost_curr"] - row["Cost_prev"]) / row["Cost_prev"]) * 100 if row["Cost_prev"] else 0

            if abs(spend_change - cpa_change) < 5 and abs(spend_change - ctr_change) < 5:
                continue

            if abs(cpa_change) >= cpa_threshold or abs(ctr_change) >= ctr_threshold:
                alerts.append({
                    level_col: row[level_col],
                    "Campaign": row["Campaign_curr"] if "Campaign_curr" in row else "",
                    "CPA Change (%)": round(cpa_change, 2),
                    "CTR Change (%)": round(ctr_change, 2),
                    "Spend Change (%)": round(spend_change, 2)
                })

            if abs(cpa_change) > 0.2 or abs(ctr_change) > 0.2:
                movers.append({
                    level_col: row[level_col],
                    "CPA Change (%)": round(cpa_change, 2),
                    "CTR Change (%)": round(ctr_change, 2)
                })
        except Exception:
            continue

    alert_df = pd.DataFrame(alerts)
    movers_df = pd.DataFrame(movers)
    if not movers_df.empty and "CPA Change (%)" in movers_df.columns:
        top_movers = movers_df.sort_values(by="CPA Change (%)", key=abs, ascending=False).head(5)
    else:
        top_movers = pd.DataFrame()
    return alert_df, top_movers

def analyze_keywords(df):
    if "Keyword" not in df.columns:
        return ""
    keyword_data = df[df["Impressions"] >= 100]
    keyword_data = keyword_data.sort_values(by="Conversions", ascending=False)
    insights = []

    if not keyword_data.empty:
        top = keyword_data.head(5)["Keyword"].tolist()
        bottom = keyword_data.tail(5)["Keyword"].tolist()
        insights.append("Top performing keywords:")
        insights.extend(top)
        insights.append("Lowest performing keywords:")
        insights.extend(bottom)

    return "\n".join(insights)

if current_file and previous_file:
    try:
        curr_df = pd.read_csv(current_file)
        prev_df = pd.read_csv(previous_file)

        required = ["CPA", "CTR", "Cost", "Conversions", "Impressions", level]
        for col in required:
            if col not in curr_df.columns or col not in prev_df.columns:
                st.error(f"Missing required column: {col}")
                st.stop()

        st.subheader("Select Campaign (Optional)")
        campaign_filter = None
        if "Campaign" in curr_df.columns:
            campaigns = sorted(curr_df["Campaign"].dropna().unique())
            campaign_filter = st.selectbox("Filter by Campaign", ["All Campaigns"] + campaigns)
            if campaign_filter != "All Campaigns":
                curr_df = curr_df[curr_df["Campaign"] == campaign_filter]
                prev_df = prev_df[prev_df["Campaign"] == campaign_filter]

        alert_df, top_movers_df = calculate_changes(curr_df, prev_df, level)

        if alert_df.empty:
            st.success("No statistically significant or unexpected changes detected.")
        else:
            st.subheader("Flagged Changes")
            st.dataframe(alert_df)

            if not top_movers_df.empty:
                st.subheader("Top Movers")
                st.dataframe(top_movers_df)

            alert_summary = alert_df.to_string(index=False)
            keyword_summary = analyze_keywords(curr_df)

            prompt = f"""
You are a digital ad performance analyst reviewing two months of Google Ads data.
The user's target CPA is ${target_cpa:.2f} and CTR is {target_ctr:.2f}%.
These are flagged performance changes at the {level} level:

{alert_summary}

{f"Keyword performance summary:\n{keyword_summary}" if keyword_summary else ""}

{f"Additional context: {custom_context}" if custom_context else ""}

Summarize what may have caused these performance changes and suggest practical optimization ideas.
Avoid commenting on expected changes caused by spend fluctuations.
"""

            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )

            st.subheader("GPT Suggestions")
            st.write(response.choices[0].message["content"])

    except Exception as e:
        st.error(f"Failed to process the files: {e}")
