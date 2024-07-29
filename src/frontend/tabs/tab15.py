import pandas as pd
import streamlit as st
from matplotlib import pyplot as plt

from config.bucket_config import Var
from src.backend.sessions.create_sessions import SessionCreator
from src.backend.state_estimation.config.vehicle_params import VehicleParams
from src.frontend.plotting.plotting import plot_data
from src.frontend.tabs.base import Tab


class Tab15(Tab):

    def __init__(self):
        super().__init__(name="tab15", description="Motor debug")

        if "data" not in self.memory:
            self.memory['data'] = pd.DataFrame()

    def build(self, session_creator: SessionCreator) -> bool:
        st.header(self.description)
        datetime_range = session_creator.r2d_session_selector(st.session_state.sessions,
                                                              key=f"{self.name} session selector")
        if st.button("Fetch this session", key=f"{self.name} fetch data button"):
            data = session_creator.fetch_data(datetime_range, verify_ssl=st.session_state.verify_ssl)
            self.memory['data'] = data

        if len(self.memory['data']) > 0:
            data = self.memory['data']

            tabs = st.tabs(tabs=["Torque", "Speed", "Temperatures", "Error code"])

            with tabs[0]:
                fig, axes = plt.subplots(2, 2, figsize=(10, 5), sharex=True, sharey=True)
                axes = axes.flatten()
                wheel_names = VehicleParams.wheel_names
                for i, ax in enumerate(axes):
                    columns = [Var.torques[i], Var.ta_torques[i]]
                    ax.plot(data[columns], label=[f"Feedback", f"Command"])
                    ax.set_title(f"{wheel_names[i]}")
                    ax.legend()
                plt.tight_layout()
                st.pyplot(fig)

                st.divider()

                plot_data(data=data, tab_name=self.name + "Torque", title="Motor Torque",
                          default_columns=Var.torques)

            with tabs[1]:
                plot_data(data=data, tab_name=self.name + "Speed", title="Motor Speed",
                          default_columns=Var.motor_speeds)

            with tabs[2]:
                plot_data(data=data, tab_name=self.name + "Motor Temperatures", title="Motor Temperatures",
                          default_columns=Var.motor_temps, simple_plot=False)
                st.divider()
                plot_data(data=data, tab_name=self.name + "VSI Temperatures", title="VSI Temperatures",
                          default_columns=Var.vsi_temps, simple_plot=False)

            with tabs[3]:
                st.dataframe(data[Var.vsi_error_codes].value_counts(), use_container_width=True)

                st.link_button("Error code description", "https://file.notion.so/f/f/b68d2f9c-7bf3-44ce-a093-ba38939a5a6a/e35e6b2b-abcf-47d9-8dc4-cb27b490464f/PDK_025786_Diagnose_en.pdf?id=0a21ff35-b780-4306-9c5f-4162f4e5c79c&table=block&spaceId=b68d2f9c-7bf3-44ce-a093-ba38939a5a6a&expirationTimestamp=1722384000000&signature=WaTrw9NmuIH6ADq0rxNu1xHJLiOF_RJY8mNwboGHsU8&downloadName=PDK_025786_Diagnose_en.pdf")

                st.divider()


                plot_data(data=data, tab_name=self.name + "Error", title="Error code",
                          default_columns=Var.vsi_error_codes)





