from datetime import datetime, timedelta
from typing import List

import pandas as pd
import streamlit as st

from config.config import ConfigLogging, ConfigLive, FSM, DataBuckets
from src.backend.api_call.influxdb_api import InfluxDbFetcher
from src.backend.data_crud.json_session_info import SessionInfoJsonCRUD
from src.backend.sessions.create_sessions import SessionCreator
from src.frontend.tabs import create_tabs, Tab, FSMStateTab, TelemetryDescriptionTab, SessionInfoTab
from stqdm import stqdm

import json

@st.experimental_dialog("Download data as CSV")
def download_data(data: pd.DataFrame):
    columns = list(data.columns)
    selected_columns = st.multiselect("Select columns to download", columns, key="download_columns")
    data = data[selected_columns]
    file_name = st.text_input("File name", value="output_data.csv", key="file_name_input")
    header = st.checkbox("Put header in downloaded data", value=True, key="header_checkbox")
    st.download_button(
        label="Download data as CSV",
        data=data.to_csv(header=header).encode("utf-8"),
        file_name=file_name,
    )


def init_sessions_state():
    if "sessions" not in st.session_state:
        st.session_state.sessions = []

    if "fetcher" not in st.session_state:
        st.session_state.fetcher = InfluxDbFetcher(config=ConfigLogging)

    if "session_creator" not in st.session_state:
        st.session_state.session_creator = SessionCreator(fetcher=st.session_state.fetcher)

    if "verify_ssl" not in st.session_state:
        st.session_state.verify_ssl = True

    if "fsm_states" not in st.session_state:
        st.session_state.fsm_states = pd.DataFrame()


if __name__ == '__main__':

    # Initialize the application
    st.set_page_config(layout="wide")
    init_sessions_state()

    cols = st.columns([5, 1])
    cols[0].title("InfluxDB data Fetcher")
    cols[0].markdown("This application allows you to fetch data from the InfluxDB database of the EPFL Racing Team")
    cols[1].image("data/img/epflrt_logo.png", width=200)

    with st.sidebar:
        # Show testing schedules
        with st.expander("Testing Schedules"):
            with open("data/test_description/schedule.json", 'r') as f:
                schedule = json.load(f)
                st.write(schedule)

        # Choose date range
        date_default = "2024-05-04"
        date = st.date_input(
            "Date", value=pd.to_datetime(date_default),
            max_value=pd.to_datetime(datetime.now().strftime("%Y-%m-%d")),
            on_change=lambda: st.session_state.pop("sessions", None),
        )
        if "session_info_crud" not in st.session_state:
            st.session_state.session_info_crud = SessionInfoJsonCRUD(f"data/test_description/session_information/{date}.json")

        # Enable / Disable SSL verification
        st.session_state.verify_ssl = st.checkbox("Fetch with SSL", value=True)
        if st.checkbox("Fetch Live Data", value=False):
            st.session_state.fetcher = InfluxDbFetcher(config=ConfigLive)
            st.session_state.session_creator = SessionCreator(fetcher=st.session_state.fetcher)
        else:
            st.session_state.fetcher = InfluxDbFetcher(config=ConfigLogging)
            st.session_state.session_creator = SessionCreator(fetcher=st.session_state.fetcher)

        # Choose FSM value to fetch
        st.divider()
        cols = st.columns([2, 1])
        fsm_values = FSM.all_states
        fsm_value = cols[0].selectbox(
            "FSM value", fsm_values, index=fsm_values.index(FSM.r2d),
            label_visibility="collapsed", key="fsm_value"
        )

        # Fetch R2D sessions
        fetch = cols[1].button(f"Fetch", key="fetch_button")
        session_creator: SessionCreator = st.session_state.session_creator

        if fetch:
            st.session_state.fsm_states = pd.DataFrame()
            dfs = session_creator.fetch_r2d_session(
                date, verify_ssl=st.session_state.verify_ssl, fsm_value=fsm_value
            )
            st.session_state.sessions = dfs
            if len(dfs) == 0:
                st.error(
                    "No R2D session found in the selected date range (if the requested data is recent, it might not have been uploaded yet)")
            else:
                st.success(f"Fetched {len(dfs)} sessions, select one in the dropdown menu")

    # Build the tabs
    if len(st.session_state.sessions) > 0:
        # Show the Telemetry Description Tab
        with st.expander("Telemetry Description"):
            telemetry_description_tab = TelemetryDescriptionTab()
            telemetry_description_tab.build(session_creator=session_creator)

        with st.expander("Session Info Modification"):
            session_info_tab = SessionInfoTab()
            session_info_tab.build(session_creator=session_creator)

        with st.expander("Sessions"):
            st.dataframe(st.session_state.sessions)

        with st.sidebar:
            st.divider()
            # Select data buckets to be fetched
            data_buckets = st.multiselect("Data Buckets", DataBuckets.all, default=DataBuckets.all, key="select_buckets")
            st.session_state.data_buckets = data_buckets

            # Select and build the tab
            tabs: dict[str, Tab] = create_tabs()
            tab_selected = st.selectbox("Select Tab", tabs.keys(), index=0, key="tab_selection")
            if st.button("Download Data to CSV"):
                download_data(data=tabs[tab_selected].memory['data'])
        tabs[tab_selected].build(session_creator=session_creator)

    with st.sidebar:
        st.divider()
        fetch_fsm = st.button("DEBUG FSM states")
        if fetch_fsm:
            st.session_state.sessions = []
            dfs = session_creator.fetch_fsm(date, verify_ssl=st.session_state.verify_ssl)
            st.session_state.fsm_states = dfs
            if len(dfs) == 0:
                st.error(
                    "No FSM states found in the selected date range (if the requested data is recent, it might not "
                    "have been uploaded yet)")
            else:
                st.success(f"Fetched {len(dfs)} states, select one or multiple in the data editor")

    if len(st.session_state.fsm_states) > 0:
        fsm_state_tab = FSMStateTab()
        fsm_state_tab.build(session_creator=session_creator)
