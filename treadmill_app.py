# ─── IMPORTS AND CONFIG ───
import streamlit as st
import pandas as pd
import base64
import os
import pytz
import json
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from calendar import monthrange
from uuid import uuid4
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ─── APP SETUP ───
st.set_page_config(page_title="My Activity Tracker", layout="centered")

LOGO_FILE = "app_logo.png"
SHEET_ID = "1beo7KZ7eDUl8tfK5DqZ0JMYiGuWApMIoVCarljUhCBo"
WORKOUT_TAB = "workouts"
SETTINGS_TAB = "settings"
TARGET_BMI = 24.9

BG_WORKOUT = "#92F6F6"
TEXT_COLOR = "#003547"
BG_EMPTY = "#eeeeee"
BORDER = "#2196f3"

# ─── ACTIVITY ICONS MAPPING ───
ACTIVITY_ICONS = {
    "Walk": "🚶",
    "Rollerblade": "⛸️",
    "Stationary Bike": "🚴",
    "Basketball (21)": "🏀",
    "Spikeball": "🏐",
    "Soccer": "⚽"
}

# ─── GOOGLE SHEETS AUTH ───
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
gcp_info = dict(st.secrets["gcp"])

# Restore correct newline format if key was escaped
if "\\n" in gcp_info["private_key"]:
    gcp_info["private_key"] = gcp_info["private_key"].replace("\\n", "\n")

credentials = ServiceAccountCredentials.from_json_keyfile_dict(gcp_info, scope)
gc = gspread.authorize(credentials)

try:
    sheet = gc.open_by_key(SHEET_ID)
except Exception as e:
    st.error(f"❌ Could not open Google Sheet: {e}")
    st.stop()

# ─── SESSION STATE INIT ───
if "page" not in st.session_state:
    st.session_state.page = "home"
if "selected_month" not in st.session_state:
    st.session_state.selected_month = datetime.today().replace(day=1)
if "selected_day" not in st.session_state:
    st.session_state.selected_day = None
if "user" not in st.session_state:
    st.session_state.user = "Default"
if "df" not in st.session_state:
    st.session_state.df = None

# ─── DATA HELPERS ───
def load_data(user_id):
    try:
        data = sheet.worksheet(WORKOUT_TAB).get_all_records()
        df = pd.DataFrame(data)
        if df.empty or "date" not in df.columns:
            return pd.DataFrame(columns=["date", "weight_lbs", "time_min", "distance_km", "vertical_feet", "calories", "activity", "user"])
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df[df["user"] == user_id]
        if "activity" not in df.columns:
            df["activity"] = "Walk"
        return df.dropna(subset=["date"])
    except Exception as e:
        st.error(f"Workout Load Error: {e}")
        return pd.DataFrame(columns=["date", "weight_lbs", "time_min", "distance_km", "vertical_feet", "calories", "activity", "user"])


def save_data(user_id, df_new_rows):
    try:
        df_new_rows["user"] = user_id
        ws = sheet.worksheet(WORKOUT_TAB)
        df_new_rows["date"] = pd.to_datetime(df_new_rows["date"]).dt.strftime("%Y-%m-%d")
        if "activity" not in df_new_rows.columns:
            df_new_rows["activity"] = "Walk"
        existing = ws.get_all_values()
        if not existing:
            ws.append_row(df_new_rows.columns.tolist())
        for row in df_new_rows[df_new_rows.columns].values.tolist():
            ws.append_row(row)
    except Exception as e:
        st.error(f"Workout Save Error: {e}")

def load_settings(user_id):
    try:
        ws = sheet.worksheet(SETTINGS_TAB)
        records = ws.get_all_records()
        for row in records:
            if row["user"] == user_id:
                return row
        default = {
            "user": user_id,
            "name": user_id,
            "goal_km": 100,
            "height_cm": 175,
            "birth_year": 1991,
            "theme": "dark",
            "gender": "Male",
            "weekly_goal": 5
        }
        save_settings(user_id, default)
        return default
    except Exception:
        return {
            "user": user_id,
            "name": user_id,
            "goal_km": 100,
            "height_cm": 175,
            "birth_year": 1991,
            "theme": "dark",
            "gender": "Male",
            "weekly_goal": 5
        }

def save_settings(user_id, settings):
    try:
        ws = sheet.worksheet(SETTINGS_TAB)
        existing = pd.DataFrame(ws.get_all_records())
        existing = existing[existing["user"] != user_id]
        combined = pd.concat([existing, pd.DataFrame([settings])], ignore_index=True)
        ws.clear()
        ws.update([combined.columns.tolist()] + combined.values.tolist())
    except Exception as e:
        st.error(f"Settings Save Error: {e}")

def parse_float(value, label, required=True):
    try:
        value = value.strip()
        if not value and not required:
            return None
        return float(value)
    except Exception:
        st.error(f"❌ Invalid input for {label}. Please enter a number.")
        return None

def get_all_users_with_names():
    try:
        records = sheet.worksheet(SETTINGS_TAB).get_all_records()
        return [(r["user"], r.get("name", r["user"])) for r in records]
    except Exception:
        return []

def get_activity_icon(activity):
    """Get the icon for a given activity type"""
    return ACTIVITY_ICONS.get(activity, "🏃")

def get_dominant_activity_for_day(df_day):
    """Get the activity with the most time for a given day"""
    if df_day.empty:
        return None
    activity_time = df_day.groupby('activity')['time_min'].sum()
    return activity_time.idxmax()

# ─── USER SELECTION ───
user_list = get_all_users_with_names()
user_ids = [uid for uid, _ in user_list]
display_names = [name for _, name in user_list]
display_names.append("➕ Add New User...")
user_ids.append("__new__")

current_user_id = st.session_state.get("user", "Default")
try:
    current_index = user_ids.index(current_user_id)
except ValueError:
    current_index = 0

selection = st.selectbox("👤 Select User", display_names, index=current_index, key="user_selector")

if user_ids[display_names.index(selection)] == "__new__":
    new_id = f"user_{uuid4().hex[:6]}"
    default = {
        "user": new_id,
        "name": new_id,
        "goal_km": 100,
        "height_cm": 175,
        "birth_year": 1991,
        "theme": "dark",
        "gender": "Male",
        "weekly_goal": 5
    }
    save_settings(new_id, default)
    st.session_state.user = new_id
    st.success("✅ New user created! Please rename in ⚙️ Settings.")
    st.session_state.df = None
    st.rerun()
else:
    if st.session_state.user != user_ids[display_names.index(selection)]:
        st.session_state.df = None
    st.session_state.user = user_ids[display_names.index(selection)]

settings = load_settings(st.session_state.user)
theme = settings.get("theme", "dark")
df = load_data(st.session_state.user) if st.session_state.df is None else st.session_state.df

# ─── LOGO ───
if os.path.exists(LOGO_FILE):
    with open(LOGO_FILE, "rb") as img_file:
        encoded = base64.b64encode(img_file.read()).decode()
    st.markdown(f"<div style='text-align:center;'><img src='data:image/png;base64,{encoded}' width='140'/></div>", unsafe_allow_html=True)

st.markdown("<h1 style='text-align:center;'>My Activity Tracker</h1>", unsafe_allow_html=True)

if st.session_state.page != "home":
    col = st.columns(3)[1]
    with col:
        if st.button("🏠 Home", key="home_top_progress"):
            st.session_state.page = "home"
            st.rerun()

# ─── LOG PAGE ───
if st.session_state.page == "log":
    st.title("🏋️ Log Activity")

    # Persist activity selection across reruns
    if "log_activity_type" not in st.session_state:
        st.session_state.log_activity_type = "Walk"

    # Enhanced activity selection with icons
    activity_options = list(ACTIVITY_ICONS.keys())
    activity_display = [f"{ACTIVITY_ICONS[act]} {act}" for act in activity_options]
    
    current_idx = activity_options.index(st.session_state.log_activity_type)
    selected_display = st.selectbox("Activity Type", activity_display, index=current_idx)
    
    # Extract activity name from display
    st.session_state.log_activity_type = selected_display.split(" ", 1)[1]
    activity = st.session_state.log_activity_type
    
    requires_distance = activity in ["Walk", "Rollerblade", "Stationary Bike"]
    requires_vertical = activity in ["Walk", "Rollerblade", "Stationary Bike"]
    needs_intensity = activity in ["Basketball (21)", "Spikeball", "Soccer"]

    with st.form("log_form"):
        date = st.date_input("Date", value=st.session_state.get("log_for_date", datetime.today()))
        last_weight = df.sort_values("date").iloc[-1]["weight_lbs"] if not df.empty else ""
        weight = st.text_input("Weight (lbs)", value=str(last_weight))
        time = st.text_input("Time (min)")

        distance = None
        unit = "km"
        if requires_distance:
            distance_col1, distance_col2 = st.columns([3, 1])
            with distance_col1:
                distance = st.text_input("Distance")
            with distance_col2:
                unit = st.radio(" ", ["miles", "km"], index=0, horizontal=True)

        vertical = st.text_input("Vertical Distance (ft)") if requires_vertical else None
        intensity = st.selectbox("Intensity", ["Low", "Moderate", "High"]) if needs_intensity else None

        submitted = st.form_submit_button("Save Activity")

        if submitted:
            if date > datetime.today().date():
                st.error("🚫 Cannot log an activity in the future.")
            else:
                w = parse_float(weight, "Weight")
                t = parse_float(time, "Time")
                d = parse_float(distance, "Distance") if distance else 0
                vert = parse_float(vertical, "Vertical Distance", required=False) if vertical else 0

                if None in [w, t]:
                    st.error("❌ Please fix the inputs.")
                else:
                    dist_km = d * 1.60934 if unit == "miles" else d
                    w_kg = w * 0.453592
                    time_hr = t / 60

                    MET = 3.5
                    if activity == "Rollerblade":
                        MET = 9.0
                    elif activity == "Stationary Bike":
                        MET = 7.5
                    elif activity == "Basketball (21)":
                        MET = {"Low": 4.5, "Moderate": 6.5, "High": 8.0}[intensity]
                    elif activity == "Spikeball":
                        MET = {"Low": 5.0, "Moderate": 6.5, "High": 8.0}[intensity]
                    elif activity == "Soccer":
                        MET = {"Low": 7.0, "Moderate": 10.0, "High": 12.0}[intensity]

                    cal_flat = MET * w_kg * time_hr
                    cal_climb = 0
                    if vert:
                        vertical_m = vert * 0.3048
                        cal_climb = (w_kg * vertical_m * 9.81) / 0.25 / 4184

                    kcal = cal_flat + cal_climb

                    parsed_date = pd.to_datetime(date)
                    new_row = {
                        "date": parsed_date.strftime("%Y-%m-%d"),
                        "weight_lbs": w,
                        "time_min": t,
                        "distance_km": dist_km,
                        "vertical_feet": vert or 0,
                        "calories": round(kcal, 2),
                        "activity": activity,
                        "user": st.session_state.user
                    }

                    df_new = pd.DataFrame([new_row])
                    save_data(st.session_state.user, df_new)
                    st.success("✅ Workout saved!")
                    st.session_state.selected_day = date
                    st.session_state.page = "home"
                    st.rerun()

# ─── HOME PAGE ───
elif st.session_state.page == "home":
    local_tz = pytz.timezone("America/Toronto")
    today = datetime.now(local_tz).date()
    current_month = st.session_state.selected_month

    st.markdown("### 📆 Monthly Activity Calendar")

    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    try:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df_week = df[(df["date"].dt.date >= start_of_week) & (df["date"].dt.date <= end_of_week)]
        weekly_count = df_week["date"].dt.date.nunique()
    except Exception:
        weekly_count = 0

    weekly_goal = settings.get("weekly_goal", 5)

    def get_week_color(count):
        return ["#8B0000", "#B22222", "#B8860B", "#FFD700", "#228B22", "#1E90FF", "#800080"][min(count, 6)]

    st.markdown(f"""
        <div style="text-align:center; font-size:26px; font-weight:bold; color:#87F3F8; margin-bottom:12px;">
            Weekly Activities:
            <span style="color:{get_week_color(weekly_count)};">{weekly_count}</span> / {weekly_goal}
        </div>
    """, unsafe_allow_html=True)

    df_month = df[df["date"].dt.strftime("%Y-%m") == current_month.strftime("%Y-%m")]

    nav1, nav2, nav3 = st.columns([1, 5, 1])
    with nav1:
        if st.button("◀️"):
            st.session_state.selected_month -= relativedelta(months=1)
            st.session_state.selected_day = None
            st.rerun()
    with nav3:
        if st.button("▶️"):
            st.session_state.selected_month += relativedelta(months=1)
            st.session_state.selected_day = None
            st.rerun()
    with nav2:
        st.markdown(f"<div style='text-align:center; font-size:18px; font-weight:bold;'>{current_month.strftime('%B %Y')}</div>", unsafe_allow_html=True)

    weekday_cols = st.columns(7)
    for i, name in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
        weekday_cols[i].markdown(f"**{name}**", unsafe_allow_html=True)

    first_day = datetime(current_month.year, current_month.month, 1).date()
    _, last_day_num = monthrange(current_month.year, current_month.month)
    last_day = datetime(current_month.year, current_month.month, last_day_num).date()

    grid_start = first_day - timedelta(days=first_day.weekday())
    grid_end = last_day + timedelta(days=(6 - last_day.weekday()))
    all_dates = [grid_start + timedelta(days=i) for i in range((grid_end - grid_start).days + 1)]
    weeks = [all_dates[i:i + 7] for i in range(0, len(all_dates), 7)]

    for week in weeks:
        cols = st.columns(7)
        for i, day in enumerate(week):
            in_current_month = day.month == current_month.month
            is_today = (day == today)
            is_selected = (st.session_state.selected_day == day)
            
            # Get workouts for this day and determine dominant activity
            df_day = df[df["date"].dt.date == day]
            has_workout = not df_day.empty
            
            # Use activity icon instead of fire emoji
            if has_workout:
                dominant_activity = get_dominant_activity_for_day(df_day)
                emoji = get_activity_icon(dominant_activity)
            else:
                emoji = ""
            
            bg_color = BG_WORKOUT if has_workout else (BG_EMPTY if in_current_month else "#cccccc")
            top_line = f"{day.day} {emoji}".strip()
            bottom_line = "📍" if is_today else ""
            btn_label = f"{top_line}{bottom_line}".strip()
            border = "2px solid #64b5f6"
            glow = "0 0 10px #00BFFF" if is_today else ""
            box_shadow = f"inset 0 0 0 3px #FF9800; box-shadow: {glow};" if is_selected or is_today else ""
            text_color = '#555555' if not in_current_month else TEXT_COLOR

            with cols[i]:
                clicked = st.button(btn_label, key=f"day_{day}")
                st.markdown(f'''
                    <style>
                    [data-testid="stButton"][key="day_{day}"] button {{
                        background-color: {bg_color};
                        color: {text_color};
                        border: {border};
                        {f'box-shadow: {glow};' if is_today and not is_selected else f'box-shadow: {box_shadow};'}
                        font-weight: bold;
                        font-size: 16px;
                        padding: 12px 0;
                        border-radius: 10px;
                        width: 100%;
                        height: 48px;
                        text-align: center;
                    }}
                    </style>
                ''', unsafe_allow_html=True)
                if clicked:
                    if has_workout:
                        st.session_state.selected_day = day
                        st.rerun()
                    else:
                        st.session_state.log_for_date = day
                        st.session_state.page = "log"
                        st.rerun()

    # ─── SELECTED DAY DETAILS ───
    if st.session_state.selected_day:
        st.markdown("---")
        selected = st.session_state.selected_day

        try:
            match = df[df["date"].dt.date == selected]
        except Exception:
            match = pd.DataFrame()

        if not match.empty:
            st.markdown(f"### 📝 Activities on {selected.strftime('%B %d')}")
            for i, (_, row) in enumerate(match.iterrows(), 1):
                activity_icon = get_activity_icon(row.get('activity', 'Walk'))
                st.markdown(f"**Activity {i}:** {activity_icon} `{row.get('activity', 'Walk')}`")
                st.markdown(f"- Duration: `{row['time_min']} min`")
                st.markdown(f"- Distance: `{row['distance_km']:.2f} km`")
                st.markdown(f"- Calories: `{row['calories']:.0f} kcal`")
                st.markdown(f"- Vertical Climb: `{row['vertical_feet']:.0f} ft`")
                if i < len(match):
                    st.markdown("---")
        else:
            st.markdown(f"### ➕ No workout logged for {selected.strftime('%B %d')}")
            if st.button("Log Workout for this Day"):
                st.session_state.log_for_date = selected
                st.session_state.page = "log"
                st.rerun()

# ─── MAIN MENU BUTTONS ───
if st.session_state.page == "home":
    menu_col = st.columns(3)[1]
    with menu_col:
        if st.button("🏋️ Log Activity", key="log_activity_btn"):
            st.session_state.page = "log"
            st.rerun()
        if st.button("📊 My Progress", key="progress_btn"):
            st.session_state.page = "progress"
            st.rerun()
        if st.button("⚙️ My Settings", key="settings_btn"):
            st.session_state.page = "settings"
            st.rerun()

# ─── SETTINGS PAGE ───
elif st.session_state.page == "settings":
    st.title("⚙️ My Settings")

    name = st.text_input("Display Name", value=settings.get("name", ""))
    height = st.number_input("Height (cm)", value=settings.get("height_cm", 175))
    birth_year = st.number_input("Birth Year", value=settings.get("birth_year", 1991))
    gender = st.selectbox("Gender", ["Male", "Female"], index=0 if settings.get("gender") == "Male" else 1)
    goal_km = st.number_input("Monthly Goal (km)", value=settings.get("goal_km", 100))
    weekly_goal = st.number_input("Weekly Workouts Goal", value=settings.get("weekly_goal", 5))
    theme = st.selectbox("Theme", ["light", "dark"], index=1 if settings.get("theme") == "dark" else 0)

    if st.button("💾 Save Settings"):
        new_settings = {
            "user": st.session_state.user,
            "name": name,
            "height_cm": height,
            "birth_year": birth_year,
            "gender": gender,
            "goal_km": goal_km,
            "weekly_goal": weekly_goal,
            "theme": theme
        }
        save_settings(st.session_state.user, new_settings)
        st.success("✅ Settings saved!")
        st.rerun()

# ─── PROGRESS PAGE ───
elif st.session_state.page == "progress":
    st.markdown("<h1 style='text-align:center;'>📊 My Progress</h1>", unsafe_allow_html=True)

    height_m = settings["height_cm"] / 100
    current_weight = df.sort_values("date").iloc[-1]["weight_lbs"] if not df.empty else 0
    current_bmi = (current_weight * 0.453592) / (height_m ** 2) if current_weight > 0 else 0
    target_weight = TARGET_BMI * (height_m ** 2) / 0.453592

    current_month = st.session_state.selected_month
    df_month = df[df["date"].dt.strftime("%Y-%m") == current_month.strftime("%Y-%m")]
    prev_month = current_month - relativedelta(months=1)
    df_prev = df[df["date"].dt.strftime("%Y-%m") == prev_month.strftime("%Y-%m")]

    def raw_delta(current, previous, unit=""):
        if previous == 0:
            return ""
        delta = current - previous
        if delta == 0:
            return "<span style='color:gray; font-size:90%; margin-left:6px;'>→ 0</span>"
        color = "green" if delta > 0 else "red"
        sign = "↑" if delta > 0 else "↓"
        return f"<span style='color:{color}; font-size:90%; margin-left:6px;'>{sign} {abs(delta):.0f}{unit}</span>"

    def percent_delta(current, previous):
        if previous == 0:
            return ""
        delta = ((current - previous) / previous) * 100
        if delta == 0:
            return "<span style='color:gray; font-size:90%; margin-left:6px;'>→ 0%</span>"
        color = "green" if delta > 0 else "red"
        sign = "↑" if delta > 0 else "↓"
        return f"<span style='color:{color}; font-size:90%; margin-left:6px;'>{sign} {abs(delta):.1f}%</span>"

    goal_km = settings["goal_km"]
    total_km = df_month["distance_km"].sum()
    total_min = df_month["time_min"].sum()
    total_kcal = df_month["calories"].sum()
    avg_speed = total_km / (total_min / 60) if total_min else 0
    workout_days = df_month["date"].dt.date.nunique()

    total_km_prev = df_prev["distance_km"].sum()
    total_min_prev = df_prev["time_min"].sum()
    total_kcal_prev = df_prev["calories"].sum()
    avg_speed_prev = total_km_prev / (total_min_prev / 60) if total_min_prev else 0
    workout_days_prev = df_prev["date"].dt.date.nunique()
    vertical_sum = df_month["vertical_feet"].sum()
    vertical_prev = df_prev["vertical_feet"].sum()

    # Goal Progress
    st.markdown("<h3 style='text-align:center; color: orange;'>Goal Progress</h3>", unsafe_allow_html=True)
    percent = min(total_km / goal_km, 1.0) if goal_km > 0 else 0
    st.markdown(f"<div style='text-align:center; font-size:20px;'><strong>{total_km:.1f} km</strong> of {goal_km} km ({percent*100:.1f}%)</div>", unsafe_allow_html=True)
    st.markdown(f"""
        <div style="background-color:#ddd; border-radius:8px; width:100%; height:30px; border: 1px solid #ccc;">
          <div style="background-color:{BG_WORKOUT}; width:{percent*100:.1f}%; height:100%; text-align:center; color:{TEXT_COLOR}; line-height:30px; font-weight:600; border-radius:8px; font-size:18px;">
            {percent*100:.1f}%
          </div>
        </div>
    """, unsafe_allow_html=True)

    # Target Weight & BMI
    if current_weight > 0:
        st.markdown("<h3 style='text-align:center; color: orange;'>Target Weight & BMI</h3>", unsafe_allow_html=True)
        st.markdown(f"📉 <strong>Current BMI:</strong> {current_bmi:.1f} vs Target: {TARGET_BMI}", unsafe_allow_html=True)
        st.markdown(f"⚖️ <strong>Current Weight:</strong> {current_weight:.1f} lbs", unsafe_allow_html=True)
        st.markdown(f"🎯 <strong>Target Weight:</strong> {target_weight:.0f} lbs", unsafe_allow_html=True)

    # ─── NEW: ACTIVITY TYPE BREAKDOWN PIE CHART ───
    if not df_month.empty:
        st.markdown("<h3 style='text-align:center; color: orange;'>🥧 Activity Type Breakdown</h3>", unsafe_allow_html=True)
        
        # Calculate time spent on each activity
        activity_time = df_month.groupby('activity')['time_min'].sum()
        
        if len(activity_time) > 0:
            fig_pie, ax_pie = plt.subplots(figsize=(8, 8))
            
            # Create labels with icons and percentages
            labels = []
            for activity, time_min in activity_time.items():
                icon = get_activity_icon(activity)
                percentage = (time_min / activity_time.sum()) * 100
                labels.append(f"{icon} {activity}\n({percentage:.1f}%)")
            
            # Use distinct colors for different activities
            colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD']
            
            wedges, texts, autotexts = ax_pie.pie(
                activity_time.values, 
                labels=labels, 
                autopct=lambda pct: f'{pct:.1f}%' if pct > 5 else '',
                colors=colors[:len(activity_time)],
                startangle=90
            )
            
            ax_pie.set_title("Time Distribution by Activity Type", fontsize=16, fontweight='bold')
            
            # Make text more readable
            for text in texts:
                text.set_fontsize(10)
            for autotext in autotexts:
                autotext.set_color('white')
                autotext.set_fontweight('bold')
                autotext.set_fontsize(9)
            
            st.pyplot(fig_pie)
            
            # Show activity summary table
            st.markdown("#### Activity Summary")
            activity_summary = df_month.groupby('activity').agg({
                'time_min': 'sum',
                'distance_km': 'sum',
                'calories': 'sum',
                'date': 'count'
            }).round(2)
            activity_summary.columns = ['Total Time (min)', 'Total Distance (km)', 'Total Calories', 'Sessions']
            
            # Add icons to the index
            activity_summary.index = [f"{get_activity_icon(activity)} {activity}" for activity in activity_summary.index]
            
            st.dataframe(activity_summary, use_container_width=True)

    # ─── NEW: ACTIVITY COMPARISON CHART ───
    if not df_month.empty:
        st.markdown("<h3 style='text-align:center; color: orange;'>⚔️ Activity Comparison</h3>", unsafe_allow_html=True)
        
        # Calculate calories per hour for each activity
        activity_comparison = df_month.groupby('activity').agg({
            'calories': 'sum',
            'time_min': 'sum',
            'distance_km': 'sum'
        })
        
        # Calculate efficiency metrics
        activity_comparison['calories_per_hour'] = (activity_comparison['calories'] / (activity_comparison['time_min'] / 60)).round(1)
        activity_comparison['avg_speed_kmh'] = (activity_comparison['distance_km'] / (activity_comparison['time_min'] / 60)).round(2)
        activity_comparison['calories_per_km'] = (activity_comparison['calories'] / activity_comparison['distance_km']).round(1)
        
        # Replace inf and NaN values
        activity_comparison = activity_comparison.replace([float('inf'), -float('inf')], 0)
        activity_comparison = activity_comparison.fillna(0)
        
        if len(activity_comparison) > 1:
            # Create comparison charts
            col1, col2 = st.columns(2)
            
            with col1:
                # Calories per hour comparison
                fig_comp1, ax_comp1 = plt.subplots(figsize=(10, 6))
                activities = list(activity_comparison.index)
                cal_per_hour = activity_comparison['calories_per_hour'].values
                
                # Create bars with activity icons as labels
                bars = ax_comp1.bar(range(len(activities)), cal_per_hour, 
                                  color=['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD'][:len(activities)])
                
                ax_comp1.set_title("🔥 Calories Burned per Hour")
                ax_comp1.set_ylabel("Calories/Hour")
                ax_comp1.set_xlabel("Activity Type")
                
                # Set x-axis labels with icons
                ax_comp1.set_xticks(range(len(activities)))
                ax_comp1.set_xticklabels([f"{get_activity_icon(act)}\n{act}" for act in activities], rotation=45, ha='right')
                
                # Add value labels on bars
                for i, bar in enumerate(bars):
                    height = bar.get_height()
                    if height > 0:
                        ax_comp1.annotate(f'{height:.0f}', 
                                        xy=(bar.get_x() + bar.get_width() / 2, height),
                                        xytext=(0, 3), textcoords="offset points", 
                                        ha='center', fontsize=10, fontweight='bold')
                
                plt.tight_layout()
                st.pyplot(fig_comp1)
            
            with col2:
                # Average speed comparison (only for activities with distance)
                speed_data = activity_comparison[activity_comparison['avg_speed_kmh'] > 0]
                
                if len(speed_data) > 0:
                    fig_comp2, ax_comp2 = plt.subplots(figsize=(10, 6))
                    speed_activities = list(speed_data.index)
                    speeds = speed_data['avg_speed_kmh'].values
                    
                    bars2 = ax_comp2.bar(range(len(speed_activities)), speeds,
                                       color=['#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#FF6B6B', '#4ECDC4'][:len(speed_activities)])
                    
                    ax_comp2.set_title("🚀 Average Speed Comparison")
                    ax_comp2.set_ylabel("Speed (km/h)")
                    ax_comp2.set_xlabel("Activity Type")
                    
                    ax_comp2.set_xticks(range(len(speed_activities)))
                    ax_comp2.set_xticklabels([f"{get_activity_icon(act)}\n{act}" for act in speed_activities], rotation=45, ha='right')
                    
                    # Add value labels on bars
                    for i, bar in enumerate(bars2):
                        height = bar.get_height()
                        if height > 0:
                            ax_comp2.annotate(f'{height:.1f}', 
                                            xy=(bar.get_x() + bar.get_width() / 2, height),
                                            xytext=(0, 3), textcoords="offset points", 
                                            ha='center', fontsize=10, fontweight='bold')
                    
                    plt.tight_layout()
                    st.pyplot(fig_comp2)
                else:
                    st.info("No distance-based activities to compare speeds")
            
            # Efficiency comparison table
            st.markdown("#### 📊 Activity Efficiency Comparison")
            efficiency_table = activity_comparison[['calories_per_hour', 'avg_speed_kmh', 'calories_per_km']].copy()
            efficiency_table.columns = ['Calories/Hour', 'Avg Speed (km/h)', 'Calories/km']
            
            # Add icons to the index
            efficiency_table.index = [f"{get_activity_icon(activity)} {activity}" for activity in efficiency_table.index]
            
            # Color code the best values in each column
            st.dataframe(efficiency_table, use_container_width=True)
            
            # Show which activity is most efficient for different goals
            st.markdown("#### 🏆 Best Activities For:")
            best_calories = activity_comparison['calories_per_hour'].idxmax()
            best_speed = activity_comparison[activity_comparison['avg_speed_kmh'] > 0]['avg_speed_kmh'].idxmax() if len(activity_comparison[activity_comparison['avg_speed_kmh'] > 0]) > 0 else "N/A"
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown(f"**🔥 Max Calories/Hour:**<br>{get_activity_icon(best_calories)} {best_calories}", unsafe_allow_html=True)
            with col2:
                if best_speed != "N/A":
                    st.markdown(f"**🚀 Highest Speed:**<br>{get_activity_icon(best_speed)} {best_speed}", unsafe_allow_html=True)
                else:
                    st.markdown("**🚀 Highest Speed:**<br>N/A", unsafe_allow_html=True)
            with col3:
                if len(activity_comparison[activity_comparison['calories_per_km'] > 0]) > 0:
                    best_efficiency = activity_comparison[activity_comparison['calories_per_km'] > 0]['calories_per_km'].idxmax()
                    st.markdown(f"**⚡ Most Efficient:**<br>{get_activity_icon(best_efficiency)} {best_efficiency}", unsafe_allow_html=True)
                else:
                    st.markdown("**⚡ Most Efficient:**<br>N/A", unsafe_allow_html=True)
        
        else:
            st.info("Need at least 2 different activity types to show comparison")

    # ─── Monthly Breakdown Charts ───
    if not df_month.empty:
        st.markdown("<h3 style='text-align:center;'>📊 Monthly Breakdown Charts</h3>", unsafe_allow_html=True)
        df_bar = df_month.sort_values("date")
        labels = df_bar["date"].dt.strftime("%d")

        # 🔥 Calories Chart
        fig1, ax1 = plt.subplots()
        bars1 = ax1.bar(labels, df_bar["calories"], color="#FF5722")
        ax1.set_title("🔥 Calories by Day")
        ax1.set_ylabel("kcal")
        ax1.set_xlabel("Day")
        for bar in bars1:
            height = bar.get_height()
            ax1.annotate(f'{height:.0f}', xy=(bar.get_x() + bar.get_width() / 2, height),
                         xytext=(0, 3), textcoords="offset points", ha='center', fontsize=8)
        st.pyplot(fig1)

        # 🛣️ Distance Chart
        fig2, ax2 = plt.subplots()
        bars2 = ax2.bar(labels, df_bar["distance_km"], color="#2196F3")
        ax2.set_title("🛣️ Distance by Day")
        ax2.set_ylabel("km")
        ax2.set_xlabel("Day")
        for bar in bars2:
            height = bar.get_height()
            ax2.annotate(f'{height:.2f}', xy=(bar.get_x() + bar.get_width() / 2, height),
                         xytext=(0, 3), textcoords="offset points", ha='center', fontsize=8)
        st.pyplot(fig2)

        # ⏱️ Duration Chart
        fig3, ax3 = plt.subplots()
        bars3 = ax3.bar(labels, df_bar["time_min"], color="#4CAF50")
        ax3.set_title("⏱️ Duration by Day")
        ax3.set_ylabel("minutes")
        ax3.set_xlabel("Day")
        for bar in bars3:
            height = bar.get_height()
            ax3.annotate(f'{height:.0f}', xy=(bar.get_x() + bar.get_width() / 2, height),
                         xytext=(0, 3), textcoords="offset points", ha='center', fontsize=8)
        st.pyplot(fig3)

    # ─── Weight Progress ───
    if not df.empty:
        st.markdown("<h3 style='text-align:center;'>⚖️ Weight Progress</h3>", unsafe_allow_html=True)
        df_weight = df[df["weight_lbs"].notnull()].sort_values("date")
        fig4, ax4 = plt.subplots()
        ax4.plot(df_weight["date"], df_weight["weight_lbs"], marker="o", linestyle="-", color="#FF9800")
        ax4.set_title("📈 Weight Over Time")
        ax4.set_ylabel("Weight (lbs)")
        ax4.set_xlabel("Date")
        ax4.grid(True)
        fig4.autofmt_xdate()
        ax4.tick_params(axis='x', labelrotation=45)
        st.pyplot(fig4)

    col = st.columns(3)[1]
    with col:
        if st.button("🏠 Home"):
            st.session_state.page = "home"
            st.rerun()
