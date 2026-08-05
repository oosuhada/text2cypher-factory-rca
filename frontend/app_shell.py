"""Streamlit page configuration and shared application styling."""

from __future__ import annotations

import streamlit as st

from frontend.design_system import build_global_css


def render_app_shell(app_title: str) -> None:
    st.set_page_config(
        page_title=app_title,
        page_icon="⬡",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.markdown(
        """
        <style>
        .block-container {padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1500px;}
        .p3-hero {
          padding: 1.4rem 1.6rem;
          border-radius: 18px;
          background: linear-gradient(120deg, #0B3B3A 0%, #0F766E 55%, #164E63 100%);
          color: white;
          box-shadow: 0 12px 30px rgba(15, 118, 110, 0.18);
          margin-bottom: 1rem;
        }
        .p3-hero h1 {font-size: 2rem; margin: 0 0 .35rem 0; color: white;}
        .p3-hero p {margin: 0; color: #D9F5F1; font-size: .98rem;}
        .p3-kicker {
          text-transform: uppercase;
          letter-spacing: .12em;
          font-size: .72rem;
          color: #99F6E4;
          margin-bottom: .45rem;
        }
        div[data-testid="stMetric"] {
          background: white;
          border: 1px solid #DDE6E8;
          padding: .8rem 1rem;
          border-radius: 14px;
        }
        div[data-testid="stPlotlyChart"] {
          overflow: visible;
          border-radius: 12px;
          padding: 0;
          background: #FFFFFF;
          box-shadow: 0 0 0 1px #DCDCDD, 0 1px 2px rgba(15, 23, 42, .035);
        }
        div[data-testid="stPlotlyChart"]:hover {
          box-shadow: 0 0 0 1px #B8C1CC, 0 1px 2px rgba(15, 23, 42, .045);
        }
        div[data-testid="stPlotlyChart"] .js-plotly-plot,
        div[data-testid="stPlotlyChart"] .plot-container,
        div[data-testid="stPlotlyChart"] .svg-container {
          border-radius: 12px;
        }
        .p3-plotly-compare-link {
          width: fit-content;
          min-height: 2.2rem;
          margin: .15rem 0 .9rem;
          padding: .45rem .7rem;
          color: #0F766E !important;
          background: #F0FDFA;
        }
        .p3-plotly-comparison-hero {
          display: grid;
          grid-template-columns: minmax(0, 1fr) auto;
          align-items: end;
          gap: 1rem;
          margin: .25rem 0 1rem;
          border: 1px solid #DCDCDD;
          border-radius: 14px;
          padding: 1.15rem 1.25rem;
          background: linear-gradient(135deg, #FFFFFF 0%, #F0FDFA 100%);
        }
        .p3-plotly-comparison-hero h1 {
          margin: .25rem 0 .4rem;
          font-size: 1.7rem;
          letter-spacing: -.035em;
        }
        .p3-plotly-comparison-hero p {
          max-width: 760px;
          margin: 0;
          color: #5F6B7B;
          font-size: .88rem;
          line-height: 1.55;
        }
        .p3-plotly-comparison-hero small {
          color: #0F766E;
          font-size: .72rem;
          font-weight: 800;
          letter-spacing: .08em;
          text-transform: uppercase;
        }
        .p3-compare-label {
          display: flex;
          align-items: center;
          justify-content: space-between;
          min-height: 2rem;
          margin: .2rem 0 .45rem;
          border-bottom: 1px solid #E5E7EB;
          color: #3A4950;
          font-size: .84rem;
          font-weight: 750;
        }
        .p3-compare-label span {
          border-radius: 999px;
          padding: .16rem .48rem;
          color: #5F6B7B;
          background: #F2F4F6;
          font-size: .66rem;
          font-weight: 800;
        }
        .p3-compare-label.is-polished span {
          color: #115E59;
          background: #CCFBF1;
        }
        .p3-comparison-notes {
          display: grid;
          grid-template-columns: repeat(4, minmax(0, 1fr));
          gap: .55rem;
          margin: .75rem 0 1rem;
        }
        .p3-comparison-notes article {
          border: 1px solid #DCDCDD;
          border-radius: 10px;
          padding: .75rem;
          background: #FFFFFF;
        }
        .p3-comparison-notes strong {
          display: block;
          margin-bottom: .22rem;
          color: #3A4950;
          font-size: .78rem;
        }
        .p3-comparison-notes span {
          color: #5F6B7B;
          font-size: .72rem;
          line-height: 1.45;
        }
        .p3-method-grid {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: .7rem;
          margin: .8rem 0 1.25rem;
        }
        .p3-method-card {
          min-width: 0;
          border: 1px solid #DCDCDD;
          border-radius: 12px;
          padding: .9rem;
          background: #FFFFFF;
        }
        .p3-method-card.is-selected {
          border-color: #0F766E;
          background: linear-gradient(145deg, #FFFFFF 0%, #F0FDFA 100%);
          box-shadow: 0 0 0 1px rgba(15,118,110,.15);
        }
        .p3-method-card header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: .5rem;
        }
        .p3-method-card header span {
          color: #5F6B7B;
          font-size: .64rem;
          font-weight: 800;
          letter-spacing: .08em;
        }
        .p3-method-card header b {
          border-radius: 999px;
          padding: .18rem .46rem;
          color: #5F6B7B;
          background: #F2F4F6;
          font-size: .64rem;
        }
        .p3-method-card.is-selected header b {
          color: #115E59;
          background: #CCFBF1;
        }
        .p3-method-card h3 {
          margin: .7rem 0 .35rem;
          color: #263238;
          font-size: 1rem;
          letter-spacing: -.02em;
        }
        .p3-method-card p {
          min-height: 3.9em;
          margin: 0;
          color: #5F6B7B;
          font-size: .75rem;
          line-height: 1.45;
        }
        .p3-method-card ul {
          display: grid;
          gap: .3rem;
          margin: .75rem 0 0;
          padding: .7rem 0 0 1rem;
          border-top: 1px solid #ECEDEF;
          color: #3A4950;
          font-size: .72rem;
          line-height: 1.4;
        }
        .p3-experiment-heading {
          display: flex;
          align-items: center;
          gap: .7rem;
          margin: 1.1rem 0 .55rem;
          border-left: 3px solid #5F6B7B;
          padding: .55rem .7rem;
          background: #F7F8F9;
        }
        .p3-experiment-heading.is-polished {
          border-left-color: #0F766E;
          background: #F0FDFA;
        }
        .p3-experiment-heading > span {
          color: #5F6B7B;
          font-size: .62rem;
          font-weight: 850;
          letter-spacing: .08em;
          white-space: nowrap;
        }
        .p3-experiment-heading div {
          display: flex;
          min-width: 0;
          flex-direction: column;
          gap: .1rem;
        }
        .p3-experiment-heading strong {
          color: #263238;
          font-size: .9rem;
        }
        .p3-experiment-heading small {
          overflow: hidden;
          color: #5F6B7B;
          font-size: .68rem;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .p3-react-runtime {
          margin: 1.5rem 0;
          border: 1px solid #DCDCDD;
          border-radius: 14px;
          padding: 1rem;
          background: #FFFFFF;
        }
        .p3-react-runtime > header,
        .p3-decision-panel > header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 1rem;
        }
        .p3-react-runtime header small,
        .p3-decision-panel header small {
          color: #0F766E;
          font-size: .64rem;
          font-weight: 850;
          letter-spacing: .08em;
        }
        .p3-react-runtime h2,
        .p3-decision-panel h2 {
          margin: .2rem 0 0;
          color: #263238;
          font-size: 1.15rem;
          letter-spacing: -.025em;
        }
        .p3-react-runtime-grid {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: .55rem;
          margin: 1rem 0;
        }
        .p3-react-runtime-grid article {
          min-width: 0;
          border: 1px solid #ECEDEF;
          border-radius: 9px;
          padding: .7rem;
          background: #F7F8F9;
        }
        .p3-react-runtime-grid b {
          display: block;
          margin-bottom: .2rem;
          color: #263238;
          font-size: .75rem;
        }
        .p3-react-runtime-grid span {
          color: #5F6B7B;
          font-size: .69rem;
          line-height: 1.4;
        }
        .p3-react-board-preview {
          overflow: hidden;
          border: 1px solid #DCDCDD;
          border-radius: 4px;
          background: #FFFFFF;
        }
        .p3-react-board-head {
          display: flex;
          min-height: 2.35rem;
          align-items: center;
          justify-content: space-between;
          gap: 1rem;
          border-bottom: 1px solid #DCDCDD;
          padding: 0 .7rem;
          color: #3A4950;
          background: #F7F8F9;
          font-size: .72rem;
          font-weight: 800;
        }
        .p3-react-board-head div {
          display: flex;
          align-items: center;
          gap: .35rem;
        }
        .p3-react-board-head i,
        .p3-react-board-head b {
          border: 1px solid #DCDCDD;
          border-radius: 3px;
          padding: .16rem .35rem;
          color: #5F6B7B;
          background: #FFFFFF;
          font-size: .6rem;
          font-style: normal;
        }
        .p3-react-board-head i {
          color: #0C1C74;
          background: rgba(12,28,116,.06);
        }
        .p3-react-board-head em {
          color: #5F6B7B;
          font-style: normal;
          letter-spacing: .08em;
        }
        .p3-react-board-body {
          display: grid;
          min-height: 240px;
          grid-template-columns: 180px minmax(0, 1fr);
        }
        .p3-react-board-body aside {
          display: flex;
          flex-direction: column;
          gap: .35rem;
          border-right: 1px solid #ECEDEF;
          padding: .8rem;
          background: #FAFBFC;
        }
        .p3-react-board-body aside strong {
          color: #5F6B7B;
          font-size: .62rem;
          letter-spacing: .06em;
          text-transform: uppercase;
        }
        .p3-react-board-body aside span {
          color: #263238;
          font-size: .82rem;
          font-weight: 800;
        }
        .p3-react-board-body aside small {
          color: #B91C1C;
          font-size: .68rem;
        }
        .p3-react-chart-schematic {
          position: relative;
          min-width: 0;
          padding: 1rem;
          background: linear-gradient(#FFFFFF,#FFFFFF) padding-box;
        }
        .p3-react-chart-schematic svg {
          position: absolute;
          inset: 20px 18px 18px;
          width: calc(100% - 36px);
          height: calc(100% - 38px);
        }
        .p3-react-chart-gridline {
          position: absolute;
          right: 18px;
          left: 18px;
          height: 1px;
          background: #ECEDEF;
        }
        .p3-react-chart-gridline.is-1 {top: 28%;}
        .p3-react-chart-gridline.is-2 {top: 52%;}
        .p3-react-chart-gridline.is-3 {top: 76%;}
        .p3-react-board-preview footer {
          display: flex;
          flex-wrap: wrap;
          gap: .4rem;
          border-top: 1px solid #ECEDEF;
          padding: .5rem .7rem;
          background: #F7F8F9;
        }
        .p3-react-board-preview footer span {
          border-radius: 999px;
          padding: .18rem .42rem;
          color: #5F6B7B;
          background: #FFFFFF;
          font-size: .62rem;
        }
        .p3-react-preview-note {
          margin: .55rem 0 0;
          color: #5F6B7B;
          font-size: .68rem;
        }
        .p3-decision-panel {
          margin: 1.5rem 0 .5rem;
          border: 1px solid #0F766E;
          border-radius: 14px;
          padding: 1rem;
          background: linear-gradient(145deg, #FFFFFF 0%, #F0FDFA 100%);
        }
        .p3-decision-panel > header > strong {
          border-radius: 999px;
          padding: .28rem .6rem;
          color: #115E59;
          background: #CCFBF1;
          font-size: .66rem;
          letter-spacing: .05em;
        }
        .p3-decision-table-wrap {
          overflow-x: auto;
          margin: 1rem 0 .7rem;
          border: 1px solid #DCDCDD;
          border-radius: 8px;
          background: #FFFFFF;
        }
        .p3-decision-table {
          width: 100%;
          min-width: 760px;
          border-collapse: collapse;
          color: #3A4950;
          font-size: .72rem;
        }
        .p3-decision-table th,
        .p3-decision-table td {
          border-bottom: 1px solid #ECEDEF;
          padding: .55rem .65rem;
          text-align: left;
          vertical-align: top;
        }
        .p3-decision-table th {
          color: #5F6B7B;
          background: #F7F8F9;
          font-size: .68rem;
          white-space: nowrap;
        }
        .p3-decision-table tbody tr:last-child td {border-bottom: 0;}
        .p3-decision-table td:first-child {font-weight: 750;}
        .p3-decision-table .is-good {color: #15803D;font-weight: 750;}
        .p3-decision-table .is-mid {color: #B45309;font-weight: 750;}
        .p3-decision-table .is-selected {color: #115E59;font-weight: 850;background: #F0FDFA;}
        .p3-decision-panel > p {
          margin: 0;
          color: #3A4950;
          font-size: .76rem;
          line-height: 1.55;
        }
        div[data-testid="stChatMessage"] {
          border: 1px solid #E2E8F0;
          border-radius: 14px;
          padding: .3rem .45rem;
        }
        .p3-status {
          display: inline-block;
          border-radius: 999px;
          padding: .18rem .55rem;
          font-size: .76rem;
          font-weight: 700;
          background: #CCFBF1;
          color: #115E59;
          margin-bottom: .45rem;
        }
        .p3-feature-grid {
          display: grid;
          grid-template-columns: repeat(4, minmax(0, 1fr));
          gap: .7rem;
          margin: .4rem 0 1rem 0;
        }
        .p3-feature {
          background: #F8FAFC;
          border: 1px solid #DDE6E8;
          border-radius: 14px;
          padding: .85rem 1rem;
        }
        .p3-feature b {color: #0F5E58; font-size: .88rem;}
        .p3-feature p {margin: .3rem 0 0 0; color: #475569; font-size: .78rem;}
        .p3-trust-strip {
          display: flex;
          flex-wrap: wrap;
          gap: .45rem;
          margin: .25rem 0 1rem 0;
        }
        .p3-trust-strip span {
          border: 1px solid #CDE5DF;
          background: #F0FDFA;
          color: #115E59;
          border-radius: 999px;
          padding: .28rem .65rem;
          font-size: .76rem;
          font-weight: 650;
        }
        .p3-section-note {
          border-left: 3px solid #14B8A6;
          background: #F8FAFC;
          padding: .65rem .8rem;
          color: #475569;
          font-size: .82rem;
          margin: .35rem 0 .9rem 0;
        }
        .p3-landing-hero {
          display: grid;
          grid-template-columns: 1.1fr .9fr;
          gap: 1rem;
          align-items: stretch;
          padding: 2.6rem;
          border-radius: 24px;
          color: white;
          background:
            radial-gradient(circle at 86% 16%, rgba(45, 212, 191, .28), transparent 34%),
            linear-gradient(135deg, #082F2C 0%, #0B4F4A 56%, #123C55 100%);
          box-shadow: 0 24px 60px rgba(8, 47, 44, .2);
          margin-bottom: 1.2rem;
        }
        .p3-landing-copy h1 {
          max-width: 720px;
          margin: .45rem 0 .9rem;
          color: white;
          font-size: clamp(2.3rem, 5vw, 4.6rem);
          line-height: .98;
          letter-spacing: -.055em;
        }
        .p3-landing-copy h1 span {display:block; color:#5EEAD4;}
        .p3-landing-copy p {
          max-width: 650px;
          margin: 0;
          color: #D6F4F0;
          font-size: 1rem;
          line-height: 1.75;
        }
        .p3-landing-proof {
          display:flex;
          flex-wrap:wrap;
          gap:.45rem;
          margin-top:1.2rem;
        }
        .p3-landing-proof span {
          border:1px solid rgba(153,246,228,.34);
          border-radius:999px;
          padding:.34rem .68rem;
          color:#CCFBF1;
          background:rgba(15,118,110,.24);
          font-size:.76rem;
          font-weight:700;
        }
        .p3-investigation {
          align-self: stretch;
          border: 1px solid rgba(255,255,255,.2);
          border-radius: 18px;
          padding: 1.1rem;
          background: rgba(3, 18, 24, .48);
          backdrop-filter: blur(14px);
        }
        .p3-investigation-head {
          display:flex;
          justify-content:space-between;
          color:#99F6E4;
          font-size:.72rem;
          letter-spacing:.06em;
          text-transform:uppercase;
        }
        .p3-investigation-question {
          margin:.9rem 0;
          border-radius:12px;
          padding:.8rem;
          color:#E6FFFB;
          background:rgba(255,255,255,.08);
          font-size:.82rem;
          line-height:1.55;
        }
        .p3-investigation-path {
          display:grid;
          grid-template-columns:1fr auto 1fr auto 1fr;
          align-items:center;
          gap:.35rem;
          color:#5EEAD4;
          font-size:.64rem;
        }
        .p3-investigation-path b {
          border:1px solid rgba(94,234,212,.3);
          border-radius:10px;
          padding:.6rem .45rem;
          color:white;
          text-align:center;
          background:rgba(15,118,110,.24);
        }
        .p3-cypher-preview {
          margin-top:.8rem;
          border-radius:10px;
          padding:.7rem;
          color:#A7F3D0;
          background:#061B20;
          font-family:ui-monospace, SFMono-Regular, Menlo, monospace;
          font-size:.65rem;
          line-height:1.55;
        }
        .p3-landing-section {
          padding:1.5rem 0 .5rem;
        }
        .p3-landing-section h2 {
          margin:.25rem 0 1rem;
          font-size:1.8rem;
          letter-spacing:-.035em;
        }
        .p3-workflow {
          display:grid;
          grid-template-columns:repeat(4,minmax(0,1fr));
          gap:.7rem;
          margin:1rem 0;
        }
        .p3-workflow div {
          border-top:2px solid #14B8A6;
          padding:.8rem .2rem;
        }
        .p3-workflow b {display:block;color:#0F5E58;}
        .p3-workflow span {color:#64748B;font-size:.76rem;}
        @media (max-width: 900px) {
          .p3-feature-grid {grid-template-columns: repeat(2, minmax(0, 1fr));}
          .p3-landing-hero {grid-template-columns:1fr;padding:1.5rem;}
          .p3-workflow {grid-template-columns:repeat(2,minmax(0,1fr));}
          .p3-plotly-comparison-hero {grid-template-columns:1fr;}
          .p3-comparison-notes {grid-template-columns:repeat(2,minmax(0,1fr));}
          .p3-method-grid {grid-template-columns:1fr;}
          .p3-method-card p {min-height:0;}
          .p3-react-runtime-grid {grid-template-columns:repeat(2,minmax(0,1fr));}
          .p3-react-board-body {grid-template-columns:1fr;}
          .p3-react-board-body aside {border-right:0;border-bottom:1px solid #ECEDEF;}
        }
        @media (max-width: 1320px) {
          .st-key-dashboard-runtime-grid [data-testid="stHorizontalBlock"] {
            flex-wrap: wrap;
          }
          .st-key-dashboard-runtime-grid [data-testid="stColumn"] {
            flex: 1 1 100% !important;
            width: 100% !important;
            min-width: 100% !important;
          }
        }
        @media (max-width: 1100px) {
          .st-key-dashboard-structure-grid [data-testid="stHorizontalBlock"],
          .st-key-dashboard-process-grid [data-testid="stHorizontalBlock"],
          .st-key-dashboard-quality-grid [data-testid="stHorizontalBlock"] {
            flex-wrap: wrap;
          }
          .st-key-dashboard-structure-grid [data-testid="stColumn"],
          .st-key-dashboard-process-grid [data-testid="stColumn"],
          .st-key-dashboard-quality-grid [data-testid="stColumn"] {
            flex: 1 1 100% !important;
            width: 100% !important;
            min-width: 100% !important;
          }
          .st-key-dashboard-primary-metrics [data-testid="stHorizontalBlock"],
          .st-key-dashboard-integrity-metrics [data-testid="stHorizontalBlock"],
          .st-key-dashboard-runtime-metrics [data-testid="stHorizontalBlock"],
          .st-key-dashboard-usage-metrics [data-testid="stHorizontalBlock"] {
            flex-wrap: wrap;
          }
          .st-key-dashboard-primary-metrics [data-testid="stColumn"],
          .st-key-dashboard-runtime-metrics [data-testid="stColumn"] {
            flex: 1 1 calc(33.333% - .7rem) !important;
            width: calc(33.333% - .7rem) !important;
            min-width: 150px !important;
          }
          .st-key-dashboard-integrity-metrics [data-testid="stColumn"],
          .st-key-dashboard-usage-metrics [data-testid="stColumn"] {
            flex: 1 1 calc(50% - .7rem) !important;
            width: calc(50% - .7rem) !important;
            min-width: 170px !important;
          }
        }
        @media (max-width: 560px) {
          .p3-comparison-notes {grid-template-columns:1fr;}
          .p3-react-runtime > header,
          .p3-decision-panel > header {align-items:flex-start;flex-direction:column;}
          .p3-react-runtime-grid {grid-template-columns:1fr;}
          .st-key-dashboard-primary-metrics [data-testid="stColumn"],
          .st-key-dashboard-integrity-metrics [data-testid="stColumn"],
          .st-key-dashboard-runtime-metrics [data-testid="stColumn"],
          .st-key-dashboard-usage-metrics [data-testid="stColumn"] {
            flex: 1 1 100% !important;
            width: 100% !important;
            min-width: 100% !important;
          }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(build_global_css(), unsafe_allow_html=True)
