import plotly.graph_objects as go
from plotly.subplots import make_subplots


def telemetry_figure(result, reference="Reference", comparison="Comparison", windows=()):
    data = result.aligned
    fig = make_subplots(rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.025,
                        row_heights=[0.3, 0.2, 0.13, 0.13, 0.24])
    channels = [("Speed", "Speed · km/h"), ("Throttle", "Throttle · %"),
                ("Brake", "Brake · on/off"), ("nGear", "Gear"), ("Delta", "Gap · s")]
    for row, (channel, title) in enumerate(channels, 1):
        if channel == "Delta":
            fig.add_trace(go.Scatter(x=data.Distance, y=data.Delta, name=f"{comparison} − {reference}",
                                    line=dict(color="#a78bfa", width=2)), row=row, col=1)
            fig.add_hline(y=0, line_dash="dot", row=row, col=1)
        else:
            for suffix, label, color in (("ref", reference, "#22d3ee"), ("cmp", comparison, "#fb923c")):
                fig.add_trace(go.Scatter(x=data.Distance, y=data[f"{channel}_{suffix}"], name=label,
                                        legendgroup=suffix, showlegend=row == 1,
                                        line=dict(color=color, width=2, shape="hv" if channel in ("Brake", "nGear") else "linear")), row=row, col=1)
        fig.update_yaxes(title_text=title, row=row, col=1)
    for number, (start, end) in enumerate(windows, 1):
        fig.add_vrect(x0=start, x1=end, fillcolor="#a78bfa", opacity=0.08, line_width=0, row="all", col=1)
        fig.add_annotation(x=(start + end) / 2, y=1, yref="paper", text=f"Section {number}", showarrow=False)
    fig.update_xaxes(title_text="Distance · m", row=5, col=1)
    fig.update_layout(height=900, template="plotly_dark", hovermode="x unified",
                      margin=dict(l=55, r=20, t=45, b=35), legend=dict(orientation="h", y=1.08))
    return fig
