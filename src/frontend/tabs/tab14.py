import numpy as np
import pandas as pd
import streamlit as st
from matplotlib import pyplot as plt
from stqdm import stqdm

from src.backend.state_estimation.config.state_estimation_param import SE_param
from src.backend.state_estimation.kalman_filters.estimation_transformation import estimate_normal_forces
from src.backend.state_estimation.kalman_filters.estimation_transformation.normal_forces import \
    estimate_aero_focre_one_tire
from src.backend.state_estimation.measurments.sensors import Sensors, get_sensors_from_data
from src.backend.state_estimation.state_estimator_app import StateEstimatorApp
from src.frontend.plotting.plotting import plot_data, plot_data_comparaison
from src.frontend.tabs import Tab
from src.backend.state_estimation.config.vehicle_params import VehicleParams
from src.backend.state_estimation.measurments.measurement_transformation.wheel_speed import measure_wheel_speeds
from src.backend.state_estimation.measurments.measurement_transformation.steering_to_wheel_angle import \
    measure_delta_wheel_angle
from src.backend.state_estimation.kalman_filters.estimation_transformation.wheel_speed import estimate_wheel_speeds
from src.backend.state_estimation.kalman_filters.estimation_transformation.longitudonal_speed import \
    estimate_longitudinal_velocities
from src.backend.state_estimation.measurments.measurement_transformation.longitudonal_tire_force import \
    measure_tire_longitudinal_forces
from src.backend.state_estimation.kalman_filters.estimation_transformation.longitudinal_tire_force import \
    estimate_longitudinal_tire_forces, traction_ellipse
from src.backend.state_estimation.measurments.measurement_transformation.wheel_acceleration import \
    measure_wheel_acceleration


class Tab14(Tab):
    acc_cols = ['sensors_aXEst', 'sensors_aYEst']
    speed_cols = ['sensors_vXEst', 'sensors_vYEst']
    motor_torques_cols = [f'VSI_TrqFeedback_{wheel}' for wheel in VehicleParams.wheel_names]
    motor_torque_pos_lim = [f'MISC_Pos_Trq_Limit_{wheel}' for wheel in VehicleParams.wheel_names]
    motor_torque_neg_lim = [f'MISC_Neg_Trq_Limit_{wheel}' for wheel in VehicleParams.wheel_names]
    max_motor_torques_cols = [f'sensors_TC_Tmax_{wheel}' for wheel in VehicleParams.wheel_names]
    min_motor_torques_cols = [f'sensors_TC_Tmin_{wheel}' for wheel in VehicleParams.wheel_names]
    motor_speeds_cols = [f'VSI_Motor_Speed_{wheel}' for wheel in VehicleParams.wheel_names]
    slip_cols = [f'sensors_s_{wheel}_est' for wheel in VehicleParams.wheel_names]

    steering_col = 'sensors_steering_angle'
    knob_mode = 'sensors_Knob3_Mode'

    def __init__(self):
        super().__init__(name="tab14", description="Skid-Pad Analysis")
        if "data" not in self.memory:
            self.memory['data'] = pd.DataFrame()

        self.wheel_speeds_cols = [f'vWheel_{wheel}' for wheel in VehicleParams.wheel_names]
        self.wheel_speeds_est_cols = [f'vWheel_{wheel}_est' for wheel in VehicleParams.wheel_names]
        self.wheel_acceleration_cols = [f'accWheel_{wheel}' for wheel in VehicleParams.wheel_names]
        self.delta_wheel_angle_cols = [f'delta_wheel_{wheel}' for wheel in VehicleParams.wheel_names]
        self.vl_cols = [f'vL_{wheel}_est' for wheel in VehicleParams.wheel_names]
        self.normal_forces_cols = [f'Fz_{wheel}_est' for wheel in VehicleParams.wheel_names]
        self.longitudinal_forces_cols = [f'Fl_{wheel}' for wheel in VehicleParams.wheel_names]
        self.longitudinal_forces_est_cols = [f'Fl_{wheel}_est' for wheel in VehicleParams.wheel_names]
        self.brake_pressure_cols = ['sensors_brake_pressure_L' for _ in range(4)]

        self.slip_cols10 = [f'sensors_s_{wheel}_est_10' for wheel in VehicleParams.wheel_names]
        self.slip_cols100 = [f'sensors_s_{wheel}_est_100' for wheel in VehicleParams.wheel_names]
        self.slip_cols1000 = [f'sensors_s_{wheel}_est_1000' for wheel in VehicleParams.wheel_names]

        self.torque_pos_cols = [f'VSI_TrqPos_{wheel}' for wheel in VehicleParams.wheel_names]
        self.torque_neg_cols = [f'VSI_TrqNeg_{wheel}' for wheel in VehicleParams.wheel_names]

        self.sampling_time = 0.01

    def create_new_feature(self):
        data = self.memory['data'].copy()

        # Create steering wheel angle and steering rad
        data[self.steering_col + "_rad"] = data[self.steering_col].map(np.deg2rad)
        data[self.delta_wheel_angle_cols] = data[[self.steering_col]].apply(
            lambda x: measure_delta_wheel_angle(x[0]), axis=1, result_type='expand')

        # Create slip10 slip100 and slip1000
        data[self.slip_cols10] = data[self.slip_cols].copy() * 10
        data[self.slip_cols100] = data[self.slip_cols].copy() * 100
        data[self.slip_cols1000] = data[self.slip_cols].copy() * 1000

        # BPF 100
        max_bpf = 35
        data['sensors_BPF_100'] = data['sensors_BPF'] * 100 / max_bpf
        data['sensors_BPF_Torque'] = data['sensors_BPF'] * 597 / max_bpf

        # Motor Torque Cmd mean
        data['sensors_Torque_cmd_mean'] = data['sensors_Torque_cmd'].copy() / 4

        # Steering angle rad
        data['steering_angle_rad'] = data['sensors_steering_angle'] * np.pi / 180

        # Create wheel speeds and longitudinal velocity
        data[self.wheel_speeds_cols] = data[self.motor_speeds_cols].apply(
            lambda x: measure_wheel_speeds(x) * VehicleParams.Rw, axis=1, result_type='expand')
        data[self.wheel_speeds_est_cols] = data[
            SE_param.estimated_states_names + self.delta_wheel_angle_cols].apply(
            lambda x: estimate_wheel_speeds(x[:9], x[9:]) * VehicleParams.Rw, axis=1, result_type='expand'
        )
        data[self.vl_cols] = data[SE_param.estimated_states_names + self.delta_wheel_angle_cols].apply(
            lambda x: estimate_longitudinal_velocities(x[:9], x[9:]), axis=1, result_type='expand'
        )

        # Create wheel acceleration and Reset wheel acceleration
        for i in range(30):
            measure_wheel_acceleration(wheel_speeds=np.array([0, 0, 0, 0], dtype=float))
        data[self.wheel_acceleration_cols] = np.array([
            measure_wheel_acceleration(wheel_speeds=wheel_speeds)
            for wheel_speeds in data[self.wheel_speeds_cols].values
        ])

        # Create Normal Forces
        data[self.normal_forces_cols] = data[SE_param.estimated_states_names].apply(
            estimate_normal_forces, axis=1, result_type='expand'
        )

        # Create Longitudinal Forces
        data[self.longitudinal_forces_cols] = data[
            self.motor_torques_cols + self.brake_pressure_cols + self.wheel_speeds_cols + self.wheel_acceleration_cols].apply(
            lambda x: measure_tire_longitudinal_forces(x[:4], x[4:8], x[8:12], x[12:]), axis=1,
            result_type='expand'
        )
        data[self.longitudinal_forces_est_cols] = data[SE_param.estimated_states_names].apply(
            lambda x: estimate_longitudinal_tire_forces(x, use_traction_ellipse=True), axis=1,
            result_type='expand'
        )

        # Compute Torque command
        data[self.torque_pos_cols] = data[self.motor_torque_pos_lim].apply(lambda x: x / 0.773, axis=1)
        data[self.torque_neg_cols] = data[self.motor_torque_neg_lim].apply(lambda x: x / 0.773, axis=1)

        # Compute delta torque
        data['Delta_Torque_feedback'] = data[self.motor_torques_cols].apply(
            lambda x: (x[0] - x[1] + x[2] - x[3]), axis=1
        )

        # Filter 0 values from RTK data and interpolate
        # rtk_columns = [col for col in data.columns if 'RTK' in col]
        # data[rtk_columns] = data[rtk_columns].replace(0, np.nan)
        # data[rtk_columns] = data[rtk_columns].interpolate(method='linear', axis=0)

        # Compute the v norm from RTK data
        # data['sensors_RTK_v_norm'] = np.sqrt(data['sensors_RTK_vx'].values ** 2 + data['sensors_RTK_vy'].values ** 2)

        # data['sensors_pitch_rate_deg'] = data['sensors_gyroY'] * (180 / np.pi)
        # data['sensors_pitch_rate_integ_deg'] = data['sensors_pitch_rate_deg'].cumsum() * self.sampling_time

        # Create trcation ellipse mu
        data['sensors_mu_est'] = data[SE_param.estimated_states_names].apply(
            lambda x: traction_ellipse(x), axis=1
        )

        self.memory['data'] = data.copy()


    def build(self, session_creator) -> bool:

        st.header(self.description)
        datetime_range = session_creator.r2d_session_selector(
            st.session_state.sessions,
            key=f"{self.name} session selector",
            session_info=True
        )

        cols = st.columns(4)
        if cols[0].button("Fetch this session", key=f"{self.name} fetch data button"):
            data = session_creator.fetch_data(datetime_range, verify_ssl=st.session_state.verify_ssl)
            self.memory['data'] = data
            with st.spinner("Creating new features"):
                self.create_new_feature()

        if len(self.memory['data']) > 0:
            cols[1].success("Data fetched")

        if cols[2].button("Create new features", key=f"{self.name} create new features"):
            with cols[2].status("Creating new features"):
                self.create_new_feature()

        if self.normal_forces_cols[0] in self.memory['data'].columns:
            cols[3].success("Created")

        st.divider()

        if len(self.memory['data']) > 0:
            data = self.memory['data']

            with st.container(border=True):
                mode_int = data[self.knob_mode].iloc[0]
                elapsed_time = data.index[-1] - data.index[0] + self.sampling_time
                arg_max_accx = data['sensors_accX'].rolling(10).mean().idxmax()
                max_accx = data['sensors_accX'].rolling(10).mean().max()
                arg_max_vx = data['sensors_vXEst'].rolling(10).mean().idxmax()
                max_vx = data['sensors_vXEst'].rolling(10).mean().max()
                mean_accx = data['sensors_accX'].mean()

                # Compute distance from velocity
                data['distance'] = data['sensors_vXEst'].cumsum() * self.sampling_time
                distance = data['distance'].iloc[-1]

                # Show metrics
                cols = st.columns([2, 2, 3, 3, 3, 3])
                cols[0].metric("Mode", VehicleParams.ControlMode[mode_int])
                cols[1].metric("Time", f"{elapsed_time:.2f} s")
                cols[2].metric("Mean AccX", f"{mean_accx:.2f} m/s²")
                cols[3].metric("Max AccX", f"{max_accx:.2f} m/s²", f"At {arg_max_accx:.2f} s", delta_color="off")
                cols[4].metric("Max VX", f"{max_vx:.2f} m/s", f"At {arg_max_vx:.2f} s", delta_color="off")
                cols[5].metric("Distance", f"{distance:.2f} m")

            st.divider()


            st.subheader("Session Overview")
            cols = st.columns(3)
            with cols[0]:
                driver_inputs_cols = ['sensors_APPS_Travel', 'sensors_BPF', 'sensors_steering_angle']
                plot_data(data=data, tab_name=self.name + "DI", title="Driver Inputs", default_columns=driver_inputs_cols, simple_plot=True)
            with cols[1]:
                car_outputs_cols = self.motor_torques_cols
                plot_data(data=data, tab_name=self.name + "CO", title="Car Outputs", default_columns=car_outputs_cols, simple_plot=True)
            with cols[2]:
                sensors_cols = ['sensors_accX', 'sensors_accY'] + self.wheel_speeds_cols
                plot_data(data=data, tab_name=self.name + "S", title="Sensors", default_columns=sensors_cols, simple_plot=True)
            st.divider()

            # Additional plots

            toggle_names = [
                "Yaw rate tracking",
                "Wheel speeds",
                "Wheel slip",
                "Wheel speeds estimation subplots",
                "Wheel speed estimation",
                "Normal forces",
                "Wheel accelerations",
                "Longitudinal forces",
                "Longitudinal forces subplots",
                "Wheel MIN/MAX Torques",
                "Wheel torques",
                "Delta torque",
            ]

            with st.expander("Additional plots"):
                with st.form(key=f"form {self.name}"):
                    nb_cols = 3
                    cols = st.columns(nb_cols)
                    toggles = {name: cols[i % nb_cols].checkbox(name, key=f"{self.name} show {name}")
                               for i, name in enumerate(toggle_names)}

                    st.form_submit_button("Submit")

            selected_toggle_names = [name for name, toggle in toggles.items() if toggle]
            tabs = st.tabs(['Acc & Speed'] + selected_toggle_names)
            tab_map = {name: tabs[i + 1] for i, name in enumerate(selected_toggle_names)}

            # PLot acceleration and speed
            with tabs[0]:
                data['v_accX_integrated'] = data['sensors_accX'].cumsum() * self.sampling_time
                plot_data(data=data, tab_name=self.name + "AS", title="Overview",
                          default_columns=['sensors_accX', 'sensors_accY'] + self.acc_cols + self.speed_cols + [
                              'v_accX_integrated'])

            # Plot yaw rate tracking
            name = toggle_names[0]
            if toggles[name]:
                with tab_map[name]:
                    plot_data_comparaison(
                        data=self.memory['data'],
                        tab_name=self.name + "_tv_reference_comparison",
                        default_columns=["sensors_gyroZ", "sensors_TV_yaw_ref"],
                        title="TV reference tracking",
                        comparison_names=["Oversteer", "Understeer"],
                        extra_columns=['steering_angle_rad'],
                    )

            # Plot wheel speeds
            name = toggle_names[1]
            if toggles[name]:
                with tab_map[name]:
                    plot_data(data=data, tab_name=self.name + "WS", title="Wheel Speeds",
                          default_columns=self.wheel_speeds_cols + self.speed_cols[:1] + ['v_accX_integrated'])

            # Plot the wheel slip
            name = toggle_names[2]
            if toggles[name]:
                with tab_map[name]:
                    plot_data(data=data, tab_name=self.name + "Slip", title="Slip Ratios", default_columns=self.slip_cols)

            # Sanity check: plot the wheel speeds estimation
            name = toggle_names[3]
            if toggles[name]:
                with tab_map[name]:
                    fig, ax = plt.subplots(2, 2, figsize=(15, 10))
                    for i, wheel in enumerate(VehicleParams.wheel_names):
                        cols = [self.wheel_speeds_cols[i], self.wheel_speeds_est_cols[i], self.vl_cols[i]]
                        data[cols].plot(ax=ax[i // 2, i % 2], title=f"Wheel {wheel} speed")
                    plt.tight_layout()
                    st.pyplot(fig)

            # Plot longitudinal force
            name = toggle_names[4]
            if toggles[name]:
                with tab_map[name]:
                    wheel = st.selectbox("Wheel", VehicleParams.wheel_names + ['all'], key=f"{self.name} wheel selection long force")
                    cols = self.wheel_speeds_cols + self.wheel_speeds_est_cols + self.vl_cols
                    if wheel != 'all':
                        cols = [col for col in cols if wheel in col]
                    plot_data(data=data, tab_name=self.name + "LF", title="Wheel velocities",
                              default_columns=cols)

            # Plot the normal forces
            name = toggle_names[5]
            if toggles[name]:
                with tab_map[name]:
                    plot_data(data=data, tab_name=self.name + "NF", title="Normal Forces",
                              default_columns=self.normal_forces_cols)

            # PLot wheel accelerations
            name = toggle_names[6]
            if toggles[name]:
                with tab_map[name]:
                    plot_data(data=data, tab_name=self.name + "WA", title="Wheel Accelerations",
                              default_columns=self.wheel_acceleration_cols)

            # Plot the longitudinal forces
            name = toggle_names[7]
            if toggles[name]:
                with tab_map[name]:
                    fig, ax = plt.subplots(2, 2, figsize=(15, 10))
                    for i, wheel in enumerate(VehicleParams.wheel_names):
                        cols = [self.longitudinal_forces_cols[i], self.longitudinal_forces_est_cols[i],
                                self.slip_cols1000[i]]
                        data[cols].plot(ax=ax[i // 2, i % 2], title=f"Wheel {wheel} longitudinal force")
                    plt.tight_layout()
                    st.pyplot(fig)

            # Plot longitudinal force
            name = toggle_names[8]
            if toggles[name]:
                with tab_map[name]:
                    wheel = st.selectbox("Wheel", VehicleParams.wheel_names + ['all'], key=f"{self.name} wheel selections long force")
                    cols = self.longitudinal_forces_cols + self.longitudinal_forces_est_cols + self.slip_cols1000
                    if wheel != 'all':
                        cols = [col for col in cols if wheel in col]
                    plot_data(data=data, tab_name=self.name + "LF" + name, title="Longitudinal Forces",
                              default_columns=cols)

            # Plot wheel torques
            name = toggle_names[9]
            if toggles[name]:
                with tab_map[name]:
                    add_slips = st.checkbox("Add slip ratios", key=f"{self.name} add slips")
                    window_size = st.number_input("Moving average window size", value=1, key=f"{self.name} window size")
                    fig, ax = plt.subplots(2, 2, figsize=(15, 10))

                    for i, wheel in enumerate(VehicleParams.wheel_names):
                        cols = [self.motor_torques_cols[i], self.max_motor_torques_cols[i], self.min_motor_torques_cols[i]]
                        if add_slips:
                            cols += [self.slip_cols1000[i]]
                        data[cols].rolling(window_size).mean().plot(ax=ax[i // 2, i % 2], title=f"Wheel {wheel} torques")
                    plt.tight_layout()
                    st.pyplot(fig)

            # Plot wheel torques
            name = toggle_names[10]
            if toggles[name]:
                with tab_map[name]:
                    plot_data(data=data, tab_name=self.name + "WT", title="Wheel Torques",
                              default_columns=self.motor_torques_cols)

            # Plot delta torque
            name = toggle_names[11]
            if toggles[name]:
                with tab_map[name]:
                    plot_data_comparaison(
                        data=data, tab_name=self.name + "DT", title="Delta Torque plot",
                        default_columns=['Delta_Torque_feedback', 'sensors_TV_delta_torque'],
                        extra_columns=[self.steering_col]
                    )