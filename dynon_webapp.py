import dash
from dash import dcc, html
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import base64
import io

app = dash.Dash(__name__)
server = app.server

# -----------------------------
# SESSION SPLITTING
# -----------------------------
def split_sessions(df):
    st = pd.to_numeric(df["Session Time"], errors="coerce")
    session_ids = []
    current = 0
    prev = None

    for val in st:
        if prev is None:
            session_ids.append(current)
        else:
            if val < prev:
                current += 1
            session_ids.append(current)
        prev = val

    df["session_id"] = session_ids
    return [df[df["session_id"] == sid].copy() for sid in sorted(df["session_id"].unique())]

# -----------------------------
# FIGURE BUILDERS
# -----------------------------
def make_flight_view(session_df):
    fig = px.scatter_geo(
        session_df,
        lat="Latitude (deg)",
        lon="Longitude (deg)",
        color="GPS Altitude (feet)",
        animation_frame="frame_index",
        hover_data=session_df.columns,
        title="Flight Path Replay"
    )
    fig.update_traces(mode="markers")
    return fig

def make_3d_path(session_df):
    fig = go.Figure(
        data=[
            go.Scatter3d(
                x=session_df["Longitude (deg)"],
                y=session_df["Latitude (deg)"],
                z=session_df["GPS Altitude (feet)"],
                mode="lines",
                line=dict(color="blue", width=4)
            )
        ]
    )
    fig.update_layout(
        title="3D Flight Path",
        scene=dict(
            xaxis_title="Longitude",
            yaxis_title="Latitude",
            zaxis_title="Altitude (ft)"
        )
    )
    return fig

def make_attitude_figs(session_df):
    figs = []
    for col in ["Pitch (deg)", "Roll (deg)", "Indicated Airspeed (knots)", "Angle of Attack (%)"]:
        if col in session_df.columns:
            figs.append(
                dcc.Graph(
                    figure=px.line(session_df, x="time_parsed", y=col, title=f"{col} vs Time")
                )
            )
    return figs

def make_all_numeric_graphs(session_df):
    figs = []
    numeric_cols = [
        col for col in session_df.columns
        if session_df[col].dtype in ["float64", "int64"]
        and col not in ["Latitude (deg)", "Longitude (deg)", "session_id", "frame_index"]
    ]
    for col in numeric_cols:
        figs.append(
            dcc.Graph(
                figure=px.line(session_df, x="time_parsed", y=col, title=f"{col} vs Time")
            )
        )
    return figs

# -----------------------------
# DASH LAYOUT
# -----------------------------
app.layout = html.Div([
    html.H1("Dynon CloudAhoy‑Style Viewer"),

    html.H3("Upload your Dynon CSV file"),
    dcc.Upload(
        id="upload-data",
        children=html.Div([
            "Drag and Drop or Click to Upload"
        ]),
        style={
            "width": "100%",
            "height": "60px",
            "lineHeight": "60px",
            "borderWidth": "2px",
            "borderStyle": "dashed",
            "borderRadius": "10px",
            "textAlign": "center",
            "margin": "10px"
        },
        multiple=False
    ),

    html.Div(id="session-select-container"),
    html.Div(id="tab-container"),
    html.Div(id="tab-content")
])

# -----------------------------
# CALLBACK: LOAD CSV + BUILD UI
# -----------------------------
@app.callback(
    dash.Output("session-select-container", "children"),
    dash.Output("tab-container", "children"),
    dash.Input("upload-data", "contents")
)
def load_csv(contents):
    if contents is None:
        return "", ""

    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    df = pd.read_csv(io.StringIO(decoded.decode('utf-8')))

    df["time_parsed"] = pd.to_datetime(df["GPS Date & Time"], errors="coerce")
    df["frame_index"] = range(len(df))

    sessions = split_sessions(df)

    session_options = [{"label": f"Session {i}", "value": i} for i in range(len(sessions))]

    dropdown = dcc.Dropdown(
        id="session-select",
        options=session_options,
        value=0,
        clearable=False
    )

    tabs = dcc.Tabs(id="tabs", value="flight", children=[
        dcc.Tab(label="Flight View", value="flight"),
        dcc.Tab(label="3D Path", value="3d"),
        dcc.Tab(label="Attitude", value="attitude"),
        dcc.Tab(label="All Data Graphs", value="allgraphs"),
    ])

    return dropdown, tabs

# -----------------------------
# CALLBACK: RENDER TAB CONTENT
# -----------------------------
@app.callback(
    dash.Output("tab-content", "children"),
    dash.Input("upload-data", "contents"),
    dash.Input("session-select", "value"),
    dash.Input("tabs", "value")
)
def render_tab(contents, session_id, tab):
    if contents is None:
        return ""

    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    df = pd.read_csv(io.StringIO(decoded.decode('utf-8')))

    df["time_parsed"] = pd.to_datetime(df["GPS Date & Time"], errors="coerce")
    df["frame_index"] = range(len(df))

    sessions = split_sessions(df)
    session_df = sessions[session_id]

    if tab == "flight":
        return dcc.Graph(figure=make_flight_view(session_df))

    if tab == "3d":
        return dcc.Graph(figure=make_3d_path(session_df))

    if tab == "attitude":
        return make_attitude_figs(session_df)

    if tab == "allgraphs":
        return make_all_numeric_graphs(session_df)

    return "No content"


if __name__ == "__main__":
    app.run_server(debug=True)
