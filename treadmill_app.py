import streamlit as st
import pandas as pd
import os
import json
import base64
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from calendar import monthrange
from uuid import uuid4

# ─── Setup ───
st.set_page_config(page_title="My Workout Tracker", layout="centered")

DATA_FOLDER = "user_data"
SETTINGS_FOLDER = "user_settings"
LOGO_FILE = "app_logo.png"
TARGET_BMI = 24.9

BG_WORKOUT = "#92F6F6"
TEXT_COLOR = "#003547"
BG_EMPTY = "#eeeeee"
BORDER = "#2196f3"

os.makedirs(DATA_FOLDER, exist_ok=True)
os.makedirs(SETTINGS_FOLDER, exist_ok=True)

# ─── Session State Init ───
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

# ─── Load / Save Helpers ───
def get_data_file(user): return os.path.join(DATA_FOLDER, f"{user}.csv")
def get_settings_file(user): return os.path.join(SETTINGS_FOLDER, f"{user}.json")

def load_data(user):
    path = get_data_file(user)
    if not os.path.exists(path):
        pd.DataFrame(columns=["date", "weight_lbs", "time_min", "distance_km", "incline", "vertical_feet", "calories"]).to_csv(path, index=False)
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    return df

def save_data(user, df):
    df.to_csv(get_data_file(user), index=False)

def load_settings(user):
    path = get_settings_file(user)
    if not os.path.exists(path):
        default = {
            "goal_km": 100,
            "height_cm": 175,
            "birth_year": 1991,
            "theme": "dark",
            "gender": "Male",
            "name": user,
            "weekly_goal": 5
        }
        with open(path, "w") as f:
            json.dump(default, f)
    with open(path, "r") as f:
        data = json.load(f)
        if "weekly_goal" not in data:
            data["weekly_goal"] = 5
        return data

def save_settings(user, settings):
    with open(get_settings_file(user), "w") as f:
        json.dump(settings, f)

# ─── User Selector ───
def get_all_users_with_names():
    users = []
    for f in os.listdir(SETTINGS_FOLDER):
        if f.endswith(".json"):
            uid = f[:-5]
            settings_data = load_settings(uid)
            users.append((uid, settings_data.get("name", uid)))
    return users

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
    save_settings(new_id, {
        "goal_km": 100,
        "height_cm": 175,
        "birth_year": 1991,
        "theme": "dark",
        "gender": "Male",
        "name": new_id,
        "weekly_goal": 5
    })
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
    df_week = df[(df["date"].dt.date >= start_of_week) & (df["date"].dt.date <= end_of_week)]
    weekly_count = df_week["date"].dt.date.nunique()
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

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
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
                    st.markdown(
                        f"""
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
                        """,
                        unsafe_allow_html=True
                    )
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
    st.title("🏋️ Log Workout")
    if st.button("🏠 Home"):
        st.session_state.page = "home"
        st.rerun()

    if st.session_state.df is None:
        st.session_state.df = load_data(st.session_state.user)

    last_weight = 230.0 if st.session_state.df.empty else st.session_state.df["weight_lbs"].iloc[-1]

    default_date = st.session_state.pop("log_for_date", None)
    if "log_for_date" not in st.session_state:
        st.session_state.log_for_date = default_date or datetime.today().date()
    elif st.session_state.log_for_date > datetime.today().date():
        st.session_state.log_for_date = datetime.today().date()

    with st.form("log_form"):
        date = st.date_input("Date", value=st.session_state.log_for_date)
        weight = st.text_input("Weight (lbs)", str(last_weight))
        time = st.text_input("Time (min)", "")
        col1, col2 = st.columns([3, 2])
        with col1:
            distance = st.text_input("Distance", "")
        with col2:
            unit = st.radio(" ", ["miles", "km"], horizontal=True, index=0)
        incline = st.text_input("Incline (%)", "")
        vertical = st.text_input("Vertical Distance (ft)", "")
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
            st.session_state.log_for_date = date
            w = parse_float(weight, "Weight")
            t = parse_float(time, "Time")
            d = parse_float(distance, "Distance")
            inc = parse_float(incline, "Incline")
            vert = parse_float(vertical, "Vertical Distance")
            if None in [w, t, d, inc, vert]:
                st.error("❌ Please fix the inputs.")
            else:
                dist_km = d * 1.60934 if unit == "miles" else d
                w_kg = w * 0.453592
                time_hr = t / 60
                MET = 8.0 if settings.get("gender", "Male") == "Male" else 7.0
                kcal = MET * w_kg * time_hr
                parsed_date = pd.to_datetime(date)
                new_row = {
                    "date": parsed_date.strftime("%Y-%m-%d"),
                    "weight_lbs": w,
                    "time_min": t,
                    "distance_km": dist_km,
                    "incline": inc,
                    "vertical_feet": vert,
                    "calories": round(kcal, 2)
                }
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row])], ignore_index=True)
                st.session_state.df["date"] = pd.to_datetime(st.session_state.df["date"], errors="coerce")
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
        to_lose = current_weight - target_weight

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
            else:
                return ""

        goal_km = settings["goal_km"]
        total_km = df_month["distance_km"].sum()
        total_min = df_month["time_min"].sum()
        total_kcal = df_month["calories"].sum()
        avg_speed = total_km / (total_min / 60) if total_min else 0
        workout_days = df_month["date"].dt.date.nunique()
        duration = str(timedelta(minutes=int(total_min)))

        total_km_prev = df_prev["distance_km"].sum()
        total_min_prev = df_prev["time_min"].sum()
        total_kcal_prev = df_prev["calories"].sum()
        avg_speed_prev = total_km_prev / (total_min_prev / 60) if total_min_prev else 0
        workout_days_prev = df_prev["date"].dt.date.nunique()
        duration_prev = str(timedelta(minutes=int(total_min_prev)))

        percent = min(total_km / goal_km, 1.0)
        st.markdown("<h4 style='color: orange;'>Goal Progress</h4>", unsafe_allow_html=True)
        st.markdown(f"<div style='font-size:20px;'>{total_km:.1f} km out of {goal_km} km ({percent*100:.1f}%)</div>", unsafe_allow_html=True)
        st.markdown(f"""
            <div style="background-color:#ddd; border-radius:8px; width:100%; height:30px; border: 1px solid #ccc;">
              <div style="background-color:{BG_WORKOUT}; width:{percent*100:.1f}%; height:100%; text-align:center; color:{TEXT_COLOR}; line-height:30px; font-weight:600; border-radius:8px; font-size:18px;">
                {percent*100:.1f}%
              </div>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("<h4 style='color: orange;'>Target Weight & BMI</h4>", unsafe_allow_html=True)
        st.markdown(f"<div style='font-size:20px;'>📉 <strong>Current BMI:</strong> {current_bmi:.1f} vs Target: {TARGET_BMI}</div>", unsafe_allow_html=True)
        st.markdown(f"<div style='font-size:20px;'>⚖️ <strong>Current Weight:</strong> {current_weight:.1f} lbs</div>", unsafe_allow_html=True)
        st.markdown(f"<div style='font-size:20px;'>🎯 <strong>Target Weight:</strong> {target_weight:.0f} lbs</div>", unsafe_allow_html=True)

        st.markdown("<h4 style='color: orange;'>Monthly Summary</h4>", unsafe_allow_html=True)
        col_curr, col_prev = st.columns(2)

        with col_curr:
            st.markdown("<div style='font-size:20px;'><strong>This Month</strong></div>", unsafe_allow_html=True)
            st.markdown(f"<div style='font-size:20px;'>🏋️ Workouts: {len(df_month)}</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='font-size:20px;'>🗓️ Active Days: {workout_days}</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='font-size:20px;'>🛣️ Distance: {total_km:.2f} km</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='font-size:20px;'>⏱️ Duration: {duration}</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='font-size:20px;'>🔥 Calories: {total_kcal:.0f} kcal</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='font-size:20px;'>🚀 Avg Speed: {avg_speed:.2f} km/h</div>", unsafe_allow_html=True)

        with col_prev:
            st.markdown(f"<div style='font-size:20px;'><strong>Last Month</strong></div>", unsafe_allow_html=True)
            st.markdown(f"<div style='font-size:20px;'>🏋️ {len(df_prev)} {stat_delta(len(df_month), len(df_prev))}</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='font-size:20px;'>🗓️ {workout_days_prev} {stat_delta(workout_days, workout_days_prev)}</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='font-size:20px;'>🛣️ {total_km_prev:.2f} km {stat_delta(total_km, total_km_prev)}</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='font-size:20px;'>⏱️ {duration_prev}</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='font-size:20px;'>🔥 {total_kcal_prev:.0f} kcal {stat_delta(total_kcal, total_kcal_prev)}</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='font-size:20px;'>🚀 {avg_speed_prev:.2f} km/h {stat_delta(avg_speed, avg_speed_prev)}</div>", unsafe_allow_html=True)

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
