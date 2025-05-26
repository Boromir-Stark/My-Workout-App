# ─── IMPORTS AND CONFIG ───
import streamlit as st
import pandas as pd
import base64
import os
import json
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from calendar import monthrange
from uuid import uuid4
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ─── APP SETUP ───
st.set_page_config(page_title="My Workout Tracker", layout="centered")

LOGO_FILE = "app_logo.png"
SHEET_ID = "1beo7KZ7eDUl8tfK5DqZ0JMYiGuWApMIoVCarljUhCBo"
WORKOUT_TAB = "workouts"
SETTINGS_TAB = "settings"
TARGET_BMI = 24.9

BG_WORKOUT = "#92F6F6"
TEXT_COLOR = "#003547"
BG_EMPTY = "#eeeeee"
BORDER = "#2196f3"

# ─── GOOGLE SHEETS AUTH ───
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
gcp_info = dict(st.secrets["gcp"])
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
            return pd.DataFrame(columns=["date", "weight_lbs", "time_min", "distance_km", "vertical_feet", "calories", "user"])
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df[df["user"] == user_id]
        return df.dropna(subset=["date"])
    except Exception as e:
        st.error(f"Workout Load Error: {e}")
        return pd.DataFrame(columns=["date", "weight_lbs", "time_min", "distance_km", "vertical_feet", "calories", "user"])

def save_data(user_id, df):
    try:
        df["user"] = user_id
        ws = sheet.worksheet(WORKOUT_TAB)
        existing = pd.DataFrame(ws.get_all_records())
        existing = existing[existing["user"] != user_id] if not existing.empty else pd.DataFrame()
        full = pd.concat([existing, df], ignore_index=True)
        for col in full.columns:
            if full[col].dtype == "datetime64[ns]":
                full[col] = full[col].dt.strftime("%Y-%m-%d")
            elif full[col].apply(lambda x: isinstance(x, pd.Timestamp)).any():
                full[col] = full[col].apply(lambda x: x.strftime("%Y-%m-%d") if isinstance(x, pd.Timestamp) else x)
        ws.clear()
        ws.update([full.columns.tolist()] + full.values.tolist())
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
        # ─── User Selection ───
def get_all_users_with_names():
    try:
        records = sheet.worksheet(SETTINGS_TAB).get_all_records()
        return [(r["user"], r.get("name", r["user"])) for r in records]
    except Exception:
        return []

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

# ─── Logo ───
if os.path.exists(LOGO_FILE):
    with open(LOGO_FILE, "rb") as img_file:
        encoded = base64.b64encode(img_file.read()).decode()
        st.markdown(f"<div style='text-align:center;'><img src='data:image/png;base64,{encoded}' width='140'/></div>", unsafe_allow_html=True)

st.markdown("<h1 style='text-align:center;'>My Workout Tracker</h1>", unsafe_allow_html=True)

# ─── Home Page ───
if st.session_state.page == "home":
    st.markdown("### 📆 Monthly Workout Calendar")
    today = datetime.today().date()
    current_month = st.session_state.selected_month

    # Weekly Tracker
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
        if count == 0: return "#8B0000"
        elif count == 1: return "#B22222"
        elif count == 2: return "#B8860B"
        elif count == 3: return "#FFD700"
        elif count == 4: return "#228B22"
        elif count == 5: return "#1E90FF"
        else: return "#800080"
    st.markdown(f"""
        <div style="text-align:center; font-size:20px; margin-bottom:12px;">
            Weekly Workouts: <span style="color:{get_week_color(weekly_count)}; font-weight:bold;">{weekly_count}</span> / {weekly_goal}
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
    first_day = current_month
    _, last_day = monthrange(first_day.year, first_day.month)
    dates = [first_day + timedelta(days=i) for i in range(last_day)]
    days_grid = [[] for _ in range(6)]
    start_wkday = first_day.weekday()
    week_idx = 0
    for _ in range(start_wkday):
        days_grid[week_idx].append(None)
    for date in dates:
        days_grid[week_idx].append(date.date())
        if len(days_grid[week_idx]) == 7:
            week_idx += 1

    for week in days_grid:
        if not week:
            continue
        cols = st.columns(7)
        for i, day in enumerate(week):
            if day:
                is_today = (day == today)
                is_selected = (st.session_state.selected_day == day)
                has_workout = not df_month[df_month["date"].dt.date == day].empty
                bg_color = BG_WORKOUT if has_workout else BG_EMPTY
                emoji = "🔥" if has_workout else ""
                border = "2px solid #64b5f6"
                glow = "0 0 10px #00BFFF" if is_today else ""
                box_shadow = f"inset 0 0 0 3px #FF9800; box-shadow: {glow};" if is_selected or is_today else ""

                with cols[i]:
                    btn_label = f"{day.day} {emoji}"
                    clicked = st.button(btn_label, key=f"day_{day}")
                    st.markdown(f'''
                        <style>
                        [data-testid="stButton"][key="day_{day}"] button {{
                            background-color: {bg_color};
                            color: {TEXT_COLOR};
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
            else:
                cols[i].markdown(" ")

    if st.session_state.selected_day:
        st.markdown("---")
        selected = st.session_state.selected_day
        match = df[df["date"].dt.date == selected]
        if not match.empty:
            row = match.iloc[0]
            st.markdown(f"### 📝 Summary for {selected.strftime('%B %d')}")
            st.markdown(f"- Duration: `{row['time_min']} min`")
            st.markdown(f"- Distance: `{row['distance_km']:.2f} km`")
            st.markdown(f"- Calories: `{row['calories']:.0f} kcal`")
            st.markdown(f"- Vertical Climb: `{row['vertical_feet']:.0f} ft`")
        else:
            st.markdown(f"### ➕ No workout logged for {selected.strftime('%B %d')}")
            if st.button("Log Workout for this Day"):
                st.session_state.log_for_date = selected
                st.session_state.page = "log"
                st.rerun()

    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🏋️ Log Workout"):
            st.session_state.page = "log"
            st.rerun()
    with col2:
        if st.button("📊 Progress"):
            st.session_state.page = "progress"
            st.rerun()
    with col3:
        if st.button("⚙️ Settings"):
            st.session_state.page = "settings"
            st.rerun()

# ─── Log Workout Page ───
elif st.session_state.page == "log":
    with st.form("log_form"):
        st.title("🏋️ Log Workout")
        if st.button("🏠 Home"):
            st.session_state.page = "home"
            st.rerun()

        date = st.date_input("Date", value=st.session_state.get("log_for_date", datetime.today().date()))
        weight = st.text_input("Weight (lbs)")
        time = st.text_input("Time (min)")
        distance = st.text_input("Distance")
        unit = st.radio("Distance Unit", ["miles", "km"], horizontal=True, index=0)
        vertical = st.text_input("Vertical Distance (ft)")

        submitted = st.form_submit_button("Save Workout")

    def parse_float(val, label):
        try:
            return float(val)
        except ValueError:
            st.warning(f"Invalid {label}")
            return None

    if submitted:
        if date > datetime.today().date():
            st.error("🚫 Cannot log a workout in the future.")
        else:
            w = parse_float(weight, "Weight")
            t = parse_float(time, "Time")
            d = parse_float(distance, "Distance")
            vert = parse_float(vertical, "Vertical Distance") if vertical.strip() else None

            if None in [w, t, d]:
                st.error("❌ Please fix the inputs.")
            else:
                dist_km = d * 1.60934 if unit == "miles" else d
                w_kg = w * 0.453592
                time_hr = t / 60
                MET = 8.0 if settings.get("gender", "Male") == "Male" else 7.0
                cal_flat = MET * w_kg * time_hr

                cal_climb = 0
                if vert is not None:
                    vertical_m = vert * 0.3048  # feet to meters
                    cal_climb = (w_kg * vertical_m * 9.81) / 0.25 / 4184

                kcal = cal_flat + cal_climb

                new_row = {
                    "date": date.strftime("%Y-%m-%d"),
                    "weight_lbs": w,
                    "time_min": t,
                    "distance_km": dist_km,
                    "vertical_feet": vert or 0,
                    "calories": round(kcal, 2),
                    "user": st.session_state.user
                }

                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row])], ignore_index=True)
                save_data(st.session_state.user, st.session_state.df)
                st.success("✅ Workout saved!")
                st.session_state.page = "home"
                st.rerun()
                # ─── Progress Page ───
elif st.session_state.page == "progress":
    st.title("📊 Progress & Summary")
    if st.button("🏠 Home"):
        st.session_state.page = "home"
        st.rerun()
    if df.empty:
        st.info("No data yet.")
    else:
        height_m = settings["height_cm"] / 100
        current_weight = df.sort_values("date").iloc[-1]["weight_lbs"]
        current_bmi = (current_weight * 0.453592) / (height_m ** 2)
        target_weight = TARGET_BMI * (height_m ** 2) / 0.453592

        current_month = st.session_state.selected_month
        df_month = df[df["date"].dt.strftime("%Y-%m") == current_month.strftime("%Y-%m")]
        prev_month = current_month - relativedelta(months=1)
        df_prev = df[df["date"].dt.strftime("%Y-%m") == prev_month.strftime("%Y-%m")]

        def stat_delta(current, previous):
            if previous == 0: return ""
            if current > previous:
                return f"<span style='color:green'>↑ {current - previous:.2f}</span>"
            elif current < previous:
                return f"<span style='color:red'>↓ {previous - current:.2f}</span>"
            return ""

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

        st.markdown("<h4 style='color: orange;'>Goal Progress</h4>", unsafe_allow_html=True)
        percent = min(total_km / goal_km, 1.0)
        st.markdown(f"<div style='font-size:20px;'>{total_km:.1f} km of {goal_km} km ({percent*100:.1f}%)</div>", unsafe_allow_html=True)
        st.markdown(f"""
            <div style="background-color:#ddd; border-radius:8px; width:100%; height:30px; border: 1px solid #ccc;">
              <div style="background-color:{BG_WORKOUT}; width:{percent*100:.1f}%; height:100%; text-align:center; color:{TEXT_COLOR}; line-height:30px; font-weight:600; border-radius:8px; font-size:18px;">
                {percent*100:.1f}%
              </div>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("<h4 style='color: orange;'>Target Weight & BMI</h4>", unsafe_allow_html=True)
        st.markdown(f"📉 **Current BMI:** {current_bmi:.1f} vs Target: {TARGET_BMI}")
        st.markdown(f"⚖️ **Current Weight:** {current_weight:.1f} lbs")
        st.markdown(f"🎯 **Target Weight:** {target_weight:.0f} lbs")

        st.markdown("<h4 style='color: orange;'>Monthly Summary</h4>", unsafe_allow_html=True)
        # Calculate vertical feet totals
        vertical_sum = df_month["vertical_feet"].sum()
        vertical_prev = df_prev["vertical_feet"].sum()

        col_curr, col_prev = st.columns(2)
        with col_curr:
            st.markdown("#### This Month")
            st.markdown(f"🏋️ Workouts: {len(df_month)}")
            st.markdown(f"🗓️ Active Days: {workout_days}")
            st.markdown(f"🛣️ Distance: {total_km:.2f} km")
            st.markdown(f"🧗 Vertical Climb: {vertical_sum:.0f} ft")
            st.markdown(f"⏱️ Duration: {total_min:.0f} min")
            st.markdown(f"🔥 Calories: {total_kcal:.0f} kcal")
            st.markdown(f"🚀 Avg Speed: {avg_speed:.2f} km/h")

        with col_prev:
            st.markdown("#### Last Month")
            st.markdown(f"🏋️ {len(df_prev)} {stat_delta(len(df_month), len(df_prev))}", unsafe_allow_html=True)
            st.markdown(f"🗓️ {workout_days_prev} {stat_delta(workout_days, workout_days_prev)}", unsafe_allow_html=True)
            st.markdown(f"🛣️ {total_km_prev:.2f} km {stat_delta(total_km, total_km_prev)}", unsafe_allow_html=True)
            st.markdown(f"🧗 {vertical_prev:.0f} ft {stat_delta(vertical_sum, vertical_prev)}", unsafe_allow_html=True)
            st.markdown(f"⏱️ {total_min_prev:.0f} min")
            st.markdown(f"🔥 {total_kcal_prev:.0f} kcal {stat_delta(total_kcal, total_kcal_prev)}", unsafe_allow_html=True)
            st.markdown(f"🚀 {avg_speed_prev:.2f} km/h {stat_delta(avg_speed, avg_speed_prev)}", unsafe_allow_html=True)

# ─── Settings Page ───
elif st.session_state.page == "settings":
    st.title("⚙️ Settings & Data")
    if st.button("🏠 Home"):
        st.session_state.page = "home"
        st.rerun()

    st.text_input("Name", value=settings.get("name", st.session_state.user), key="new_name")
    goal_km = st.number_input("Monthly Distance Goal (km)", min_value=10, max_value=1000, value=settings["goal_km"])
    weekly_goal = st.number_input("Weekly Workout Goal", min_value=1, max_value=14, value=settings.get("weekly_goal", 5))
    height_cm = st.number_input("Height (cm)", value=settings["height_cm"], min_value=100, max_value=250)
    birth_year = st.number_input("Birth Year", value=settings["birth_year"], min_value=1900, max_value=datetime.today().year)
    gender = st.selectbox("Gender", ["Male", "Female"], index=0 if settings["gender"] == "Male" else 1)
    theme_choice = st.radio("Theme", ["Light", "Dark"], index=0 if settings["theme"] == "light" else 1)

    st.markdown("### 🗂️ Manage Workout Logs")
    logs = load_data(st.session_state.user)
    if not logs.empty:
        log_dates = logs["date"].dt.strftime("%B %d, %Y").tolist()
        selected_log = st.selectbox("Select Workout to Delete", log_dates)
        if st.button("Delete Selected Workout"):
            log_to_delete = logs[logs["date"].dt.strftime("%B %d, %Y") == selected_log]
            if not log_to_delete.empty:
                log_date = log_to_delete["date"].iloc[0]
                logs = logs[logs["date"] != log_date]
                save_data(st.session_state.user, logs)
                st.success(f"✅ Workout on {selected_log} deleted.")
            else:
                st.warning("No workout found for this date.")
    else:
        st.info("No workouts logged yet.")

    if st.button("Save Settings"):
        settings.update({
            "name": st.session_state.new_name,
            "goal_km": goal_km,
            "weekly_goal": weekly_goal,
            "height_cm": height_cm,
            "birth_year": birth_year,
            "gender": gender,
            "theme": theme_choice.lower()
        })
        save_settings(st.session_state.user, settings)
        st.success("✅ Settings updated!")


