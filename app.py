import sqlite3
import pandas as pd
import streamlit as st
from datetime import datetime

# ---------------------------
# Streamlit page config
# ---------------------------
st.set_page_config(page_title="Local Food Wastage Management", layout="wide")

DB_PATH = "food_wastage.db"  # Keep DB and app.py in same folder


# ---------------------------
# Database Functions
# ---------------------------
@st.cache_resource
def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def run_query(query, params=(), as_df=True):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(query, params)
    if as_df:
        cols = [desc[0] for desc in cur.description] if cur.description else []
        rows = cur.fetchall()
        return pd.DataFrame(rows, columns=cols)
    else:
        conn.commit()
        return None


def run_write(query, params=()):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(query, params)
    conn.commit()
    return cur.lastrowid


def load_table(table_name):
    return run_query(f"SELECT * FROM {table_name}")


# ---------------------------
# Sidebar Filters
# ---------------------------
st.sidebar.title("Filters")

providers_df = load_table("Providers")
receivers_df = load_table("Receivers")
food_df = load_table("Food_Listings")
claims_df = load_table("Claims")

city_options = sorted(list(set(providers_df["City"].dropna().tolist() + food_df["Location"].dropna().tolist())))
provider_types = sorted(providers_df["Type"].dropna().unique().tolist())
food_types = sorted(food_df["Food_Type"].dropna().unique().tolist())
meal_types = sorted(food_df["Meal_Type"].dropna().unique().tolist())

f_city = st.sidebar.selectbox("City", ["All"] + city_options, index=0)
f_provider_type = st.sidebar.selectbox("Provider Type", ["All"] + provider_types, index=0)
f_food_type = st.sidebar.selectbox("Food Type", ["All"] + food_types, index=0)
f_meal_type = st.sidebar.selectbox("Meal Type", ["All"] + meal_types, index=0)

st.sidebar.markdown("---")
st.sidebar.caption("Tip: Filter lagake 'Browse Listings' me results dekho.")

# ---------------------------
# Tabs
# ---------------------------
st.title("🍽️ Local Food Wastage Management System")
tabs = st.tabs(["📊 Dashboard", "🗂️ Browse Listings", "🤝 Make a Claim", "🛠️ Admin (CRUD)", "🔎 Analysis (SQL)"])

# ---------------------------
# Dashboard
# ---------------------------
with tabs[0]:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Providers", len(providers_df))
    c2.metric("Total Receivers", len(receivers_df))
    c3.metric("Food Listings", len(food_df))
    c4.metric("Claims", len(claims_df))

    st.markdown("#### Recently Added Listings")
    recent_listings = run_query("""
        SELECT Food_ID, Food_Name, Quantity, Expiry_Date, Location, Food_Type, Meal_Type, Provider_ID
        FROM Food_Listings
        ORDER BY Food_ID DESC
        LIMIT 10
    """)
    st.dataframe(recent_listings, use_container_width=True)


# ---------------------------
# Filter Function
# ---------------------------
def apply_filters(df):
    if df.empty:
        return df
    if f_city != "All":
        df = df[df["Location"] == f_city]
    if f_provider_type != "All":
        df = df[df["Provider_Type"] == f_provider_type]
    if f_food_type != "All":
        df = df[df["Food_Type"] == f_food_type]
    if f_meal_type != "All":
        df = df[df["Meal_Type"] == f_meal_type]
    return df


# ---------------------------
# Browse Listings
# ---------------------------
with tabs[1]:
    st.subheader("Available Food Listings")
    listings = run_query("""
        SELECT f.Food_ID, f.Food_Name, f.Quantity, f.Expiry_Date, f.Location, f.Food_Type, f.Meal_Type,
               p.Name AS Provider_Name, p.Type AS Provider_Type, p.Contact AS Provider_Contact
        FROM Food_Listings f
        LEFT JOIN Providers p ON p.Provider_ID = f.Provider_ID
    """)
    listings = apply_filters(listings)
    st.dataframe(listings, use_container_width=True)

# ---------------------------
# Make a Claim
# ---------------------------
with tabs[2]:
    st.subheader("Create a Claim")
    if not receivers_df.empty and not food_df.empty:
        rx_map = {f'{row["Name"]} ({row["City"]})': int(row["Receiver_ID"]) for _, row in receivers_df.iterrows()}
        selected_rx = st.selectbox("Select Receiver", list(rx_map.keys()))

        fx_map = {f'{row["Food_Name"]} | {row["Location"]} (Qty: {row["Quantity"]})': int(row["Food_ID"]) for _, row in
                  food_df.iterrows()}
        selected_food = st.selectbox("Select Food Item", list(fx_map.keys()))

        status_opt = ["Pending", "Completed", "Cancelled"]
        claim_status = st.selectbox("Status", status_opt, index=0)

        if st.button("Submit Claim", type="primary"):
            run_write("INSERT INTO Claims (Food_ID, Receiver_ID, Status, Timestamp) VALUES (?, ?, ?, ?)",
                      (fx_map[selected_food], rx_map[selected_rx], claim_status,
                       datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            st.success("Claim created successfully!")

# ---------------------------
# Admin (CRUD)
# ---------------------------
with tabs[3]:
    st.subheader("Admin – Add Provider")
    ap_name = st.text_input("Name")
    ap_type = st.text_input("Type")
    ap_addr = st.text_area("Address")
    ap_city = st.text_input("City")
    ap_contact = st.text_input("Contact")
    if st.button("Add Provider"):
        run_write("INSERT INTO Providers (Name, Type, Address, City, Contact) VALUES (?, ?, ?, ?, ?)",
                  (ap_name, ap_type, ap_addr, ap_city, ap_contact))
        st.success("Provider added successfully!")

# ---------------------------
# Analysis (SQL Queries Output)
# ---------------------------
with tabs[4]:
    st.subheader("📊 Analysis – SQL Query Results")

    queries = {
        "Providers per City": "SELECT City, COUNT(*) AS Total_Providers FROM Providers GROUP BY City",
        "Receivers per City": "SELECT City, COUNT(*) AS Total_Receivers FROM Receivers GROUP BY City",
        "Top Provider Types": "SELECT Type, COUNT(*) AS Contribution_Count FROM Providers GROUP BY Type ORDER BY Contribution_Count DESC",
        "Top Food Types": "SELECT Food_Type, COUNT(*) AS Count FROM Food_Listings GROUP BY Food_Type ORDER BY Count DESC",
        "Claims Status %": "SELECT Status, COUNT(*)*100.0/(SELECT COUNT(*) FROM Claims) AS Percentage FROM Claims GROUP BY Status",
        "Top Meal Types Claimed": """
            SELECT Meal_Type, COUNT(*) AS Total_Claims
            FROM Food_Listings f
            JOIN Claims c ON f.Food_ID = c.Food_ID
            GROUP BY Meal_Type
            ORDER BY Total_Claims DESC
        """
    }

    selected_analysis = st.selectbox("Select Analysis", list(queries.keys()))
    st.dataframe(run_query(queries[selected_analysis]), use_container_width=True)
