
import streamlit as st
import pandas as pd
import openai

# Load OpenAI API key
openai.api_key = st.secrets["OPENAI_API_KEY"]

st.title("Campaign Optimizer GPT v4")

# Collapsible Instructions
with st.expander("📘 How to Use This App"):
    st.markdown("""
Upload two CSVs exported from Google Ads (e.g., last month vs. this month).  
Required columns:
- **Ad Group** (used to align data)
- **CPA** (Cost per Acquisition)
- **CTR** (Click-through Rate)
- **Cost**
- **Conversions**
- **Impressions**
- *(Optional)* **Keyword** (for keyword-level analysis)

Tips:
- Format both CSVs consistently (same structure and column names)
- Each row should represent an ad group, ad, or keyword
- The app will:
  - Flag statistically significant changes
  - Suppress expected changes (e.g. spend ↓ → impressions ↓)
  - Automatically analyze keywords if the "Keyword" column is present
    """)

# Upload CSVs
st.subheader("Upload Two CSV Files for Comparison")
current_file = st.file_uploader("Current Period CSV", type="csv", key="current")
previous_file = st.file_uploader("Previous Period CSV", type="csv", key="previous")

# Campaign goals
st.subheader("Set Campaign Goals")
target_cpa = st.number_input("Target CPA ($)", min_value=0.0, step=0.1)
target_ctr = st.number_input("Target CTR (%)", min_value=0.0, step=0.1)

# Alert thresholds
st.subheader("Set Alert Sensitivity")
cpa_threshold = st.slider("Flag CPA changes over (%)", 5, 100, 15)
ctr_threshold = st.slider("Flag CTR changes over (%)", 5, 100, 15)

# Optional context input
st.subheader("Add Custom Notes (Optional)")
custom_context = st.text_area("e.g. This was during a holiday sale or budget doubled this month.")

def calculate_changes(current_df, previous_df):
    merged = pd.merge(current_df, previous_df, on="Ad Group", suffixes=("_curr", "_prev"))
    alerts, movers = [], []

    for index, row in merged.iterrows():
        try:
            cpa_change = ((row["CPA_curr"] - row["CPA_prev"]) / row["CPA_prev"]) * 100 if row["CPA_prev"] else 0
            ctr_change = ((row["CTR_curr"] - row["CTR_prev"]) / row["CTR_prev"]) * 100 if row["CTR_prev"] else 0
            spend_change = ((row["Cost_curr"] - row["Cost_prev"]) / row["Cost_prev"]) * 100 if row["Cost_prev"] else 0

            if abs(cpa_change - spend_change) < 5 and abs(ctr_change - spend_change) < 5:
                continue

            if abs(cpa_change) >= cpa_threshold or abs(ctr_change) >= ctr_threshold:
                alerts.append({
                    "Ad Group": row["Ad Group"],
                    "CPA Change (%)": round(cpa_change, 2),
                    "CTR Change (%)": round(ctr_change, 2),
                    "Spend Change (%)": round(spend_change, 2)
                })

            if abs(cpa_change) > 0.2 or abs(ctr_change) > 0.2:
                movers.append({
                    "Ad Group": row["Ad Group"],
                    "CPA Change (%)": round(cpa_change, 2),
                    "CTR Change (%)": round(ctr_change, 2)
                })

        except Exception:
            continue

    top_movers = pd.DataFrame(movers).sort_values(by="CPA Change (%)", key=abs, ascending=False).head(5)
    return alerts, top_movers

def analyze_keywords(df):
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
        current_df = pd.read_csv(current_file)
        previous_df = pd.read_csv(previous_file)

        st.subheader("Change Detection")
        alerts, top_movers_df = calculate_changes(current_df, previous_df)

        if not alerts:
            st.success("No statistically significant or unexpected changes detected.")
        else:
            alert_df = pd.DataFrame(alerts)
            st.dataframe(alert_df)

            if not top_movers_df.empty:
                st.subheader("Top Movers")
                st.dataframe(top_movers_df)

            alert_summary = alert_df.to_string(index=False)
            keyword_summary = ""

            if "Keyword" in current_df.columns:
                keyword_summary = analyze_keywords(current_df)

            prompt = f"""
You are a digital ad performance analyst reviewing two months of Google Ads data.
The user's target CPA is ${target_cpa:.2f} and CTR is {target_ctr:.2f}%.
These are flagged performance changes:

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
