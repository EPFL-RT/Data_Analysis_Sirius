from datetime import datetime, timedelta
from typing import List

import pandas as pd
import streamlit as st

from config.config import ConfigLogging, ConfigLive, FSM, DataBuckets
from src.backend.api_call.influxdb_api import InfluxDbFetcher
from src.backend.data_crud.json_session_info import SessionInfoJsonCRUD
from src.backend.sessions.create_sessions import SessionCreator
from src.frontend.tabs import create_tabs, Tab, FSMStateTab, TelemetryDescriptionTab, SessionInfoTab
from src.frontend.dialogue_boxes.dialogue_box import create_dialogue_box
from stqdm import stqdm
import json


def show_testing_schedule():
    with open("data/test_description/schedule.json", 'r') as f:
        st.subheader("Testing Schedule")
        schedule = json.load(f)
        st.write(schedule)


def init_sessions_state():
    if "sessions" not in st.session_state:
        st.session_state.sessions = pd.DataFrame()

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
        with st.expander("Select Date and Config", expanded=len(st.session_state.sessions) == 0):
            # Show testing schedules
            st.button("Show Testing Schedule", on_click=show_testing_schedule)

            # Choose date range
            date_default = "2024-05-04"
            date = st.date_input(
                "Date", value=pd.to_datetime(date_default),
                max_value=pd.to_datetime(datetime.now().strftime("%Y-%m-%d")),
                on_change=lambda: [st.session_state.pop("sessions", None),
                 st.session_state.pop("session_info_crud", None)],
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
        # Show the Fetched Session and their descriptions
        with st.expander("Sessions"):
            if 'description' not in st.session_state.sessions.columns:
                if st.button("Get session info"):
                    crud = st.session_state.session_info_crud
                    session_infos = {key: crud.read(key) for key in st.session_state.sessions.index}
                    st.session_state.session_info_data = pd.DataFrame(session_infos).T
                    st.session_state.sessions = pd.concat(
                        [st.session_state.sessions, st.session_state.session_info_data], axis=1
                    )
            st.dataframe(st.session_state.sessions.drop(columns=['start', 'end']), use_container_width=True)

        with st.sidebar:
            with st.expander("Data Buckets & Dialogue Box", expanded=True):
                # Select data buckets to be fetched
                data_buckets = st.multiselect("Data Buckets", DataBuckets.all, default=DataBuckets.all, key="select_buckets")
                st.session_state.data_buckets = data_buckets

                # Select and build the tab
                tabs: dict[str, Tab] = create_tabs()
                tab_selected = st.selectbox("Select Tab", tabs.keys(), index=0, key="tab_selection")
                tab = tabs[tab_selected]
                if st.button("Open Dialogue Box"):
                    if len(tab.memory['data']) > 0:
                        create_dialogue_box(tab=tab)
                    else:
                        st.error("No data fetched yet, please fetch data first")
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