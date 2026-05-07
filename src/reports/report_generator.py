import csv
import io
import sys
import os
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
from fpdf import FPDF

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.database.repository import DatabaseRepository


def _safe(text: str) -> str:
    # trips non-latin1 characters so Helvetica doesn't crash
    return text.encode("latin-1", errors="replace").decode("latin-1")


class SafeNetPDF(FPDF):
    # custom PDF class with SafeNet branding

    def header(self):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(100, 100, 100)
        self.cell(0, 8, "SafeNet - Cyberbullying Detection Report", align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(60, 60, 180)
        self.set_line_width(0.4)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}  |  Generated {datetime.now():%Y-%m-%d %H:%M}", align="C")

    def section_title(self, title: str):
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(30, 30, 80)
        self.ln(4)
        self.cell(0, 10, _safe(title), new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(60, 60, 180)
        self.line(10, self.get_y(), 80, self.get_y())
        self.ln(4)

    def body_text(self, text: str):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(40, 40, 40)
        self.multi_cell(0, 6, _safe(text))
        self.ln(2)

    def add_table(self, headers: list[str], rows: list[list[str]], col_widths: list[int] | None = None):
        # draws a simple table
        if col_widths is None:
            col_widths = [int(190 / len(headers))] * len(headers)

        # header row
        self.set_font("Helvetica", "B", 9)
        self.set_fill_color(45, 45, 100)
        self.set_text_color(255, 255, 255)
        for i, h in enumerate(headers):
            self.cell(col_widths[i], 8, h, border=1, fill=True, align="C")
        self.ln()

        # data rows
        self.set_font("Helvetica", "", 9)
        self.set_text_color(40, 40, 40)
        fill = False
        for row in rows:
            if self.get_y() > 260:
                self.add_page()
            if fill:
                self.set_fill_color(235, 235, 245)
            else:
                self.set_fill_color(255, 255, 255)
            for i, cell_val in enumerate(row):
                self.cell(col_widths[i], 7, _safe(str(cell_val)[:40]), border=1, fill=True, align="C")
            self.ln()
            fill = not fill


class ReportGenerator:
    # generates downloadable reports (CSV/PDF) for parents and administrators.
    def __init__(self, db_repo: DatabaseRepository):
        self.db_repo = db_repo

    # ── CSV Exports ─────────────────────────────────────────────────────────

    def generate_alerts_csv(self, output_path: str = "alerts_report.csv"):
        alerts = self.db_repo.get_all_alerts()
        with open(output_path, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(["Alert ID", "Timestamp", "User ID", "Username", "Severity", "Reason"])
            for alert in alerts:
                writer.writerow(alert)

    def generate_top_offenders_txt(self, output_path: str = "top_offenders.txt"):
        users = self.db_repo.get_top_risky_users(limit=10)
        with open(output_path, mode='w', encoding='utf-8') as file:
            file.write("--- SafeNet: Top Risky Users Report ---\n\n")
            for u in users:
                user_id, username, risk, flagged, total = u
                file.write(f"User: {username} ({user_id})\n")
                file.write(f"Risk Score: {risk:.2f}\n")
                file.write(f"Flagged Messages: {flagged} / {total}\n")
                file.write("-" * 40 + "\n")

    # ── PDF Report ──────────────────────────────────────────────────────────

    def generate_pdf_report(self) -> bytes:
        # generates a comprehensive PDF report and returns it as bytes
        stats = self.db_repo.get_summary_stats()
        alerts = self.db_repo.get_all_alerts()
        top_users = self.db_repo.get_top_risky_users(limit=10)
        victims = self.db_repo.get_victim_summary()

        pdf = SafeNetPDF()
        pdf.alias_nb_pages()
        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.add_page()

        # ── cover / title ───────────────────────────────────────────────────
        pdf.set_font("Helvetica", "B", 28)
        pdf.set_text_color(30, 30, 80)
        pdf.ln(30)
        pdf.cell(0, 15, "SafeNet Analysis Report", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 12)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 10, f"Generated: {datetime.now():%B %d, %Y at %H:%M}", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(10)

        # ── executive summary ────────────────────────────────────────────
        pdf.section_title("1. Executive Summary")
        flagged_pct = (stats['flagged_messages'] / stats['total_messages'] * 100) if stats['total_messages'] > 0 else 0
        summary = (
            f"SafeNet analyzed {stats['total_messages']} messages across {stats['total_users']} users. "
            f"Of those, {stats['flagged_messages']} messages ({flagged_pct:.1f}%) were flagged as potentially toxic. "
            f"The system generated {stats['total_alerts']} alerts, of which {stats['critical_alerts']} are CRITICAL severity."
        )
        pdf.body_text(summary)

        if stats['critical_alerts'] > 0:
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(200, 0, 0)
            pdf.cell(0, 8, "WARNING: Critical alerts require immediate attention.", new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(40, 40, 40)
            pdf.ln(4)

        # ── alert summary table ──────────────────────────────────────────
        pdf.section_title("2. Alert Log")
        if alerts:
            headers = ["ID", "Time", "User", "Severity", "Reason"]
            rows = []
            for a in alerts:
                rows.append([a[0], a[1][:19], a[3], a[4], a[5][:35]])
            pdf.add_table(headers, rows, col_widths=[20, 35, 25, 25, 85])
        else:
            pdf.body_text("No alerts were generated during this analysis session.")

        # ── top offenders ────────────────────────────────────────────────
        pdf.add_page()
        pdf.section_title("3. Top Offenders")
        if top_users:
            headers = ["Username", "Risk Score", "Flagged", "Total Msgs"]
            rows = []
            for u in top_users:
                rows.append([u[1], f"{u[2]:.2f}", str(u[3]), str(u[4])])
            pdf.add_table(headers, rows, col_widths=[50, 40, 40, 50])
        else:
            pdf.body_text("No high-risk users were identified.")

        # ── victim analysis ──────────────────────────────────────────────
        pdf.section_title("4. Victim Analysis")
        if victims:
            pdf.body_text(
                "The following users were identified as primary targets of abusive messages. "
                "Multiple distinct aggressors targeting the same person may indicate coordinated harassment (gang-up behavior)."
            )
            headers = ["Victim", "Times Targeted", "Distinct Aggressors"]
            rows = []
            for v in victims:
                rows.append([v[1], str(v[2]), str(v[3])])
            pdf.add_table(headers, rows, col_widths=[60, 60, 60])

            # Detail: flagged messages for the top victim
            top_victim_id = victims[0][0]
            top_victim_name = victims[0][1]
            targeted_msgs = self.db_repo.get_messages_targeting_user(top_victim_id)
            if targeted_msgs:
                pdf.ln(4)
                pdf.set_font("Helvetica", "B", 11)
                pdf.set_text_color(30, 30, 80)
                pdf.cell(0, 8, _safe(f"Evidence: Flagged messages targeting {top_victim_name}"), new_x="LMARGIN", new_y="NEXT")
                pdf.ln(2)
                for tm in targeted_msgs[:15]:  # Limit to 15 for readability
                    pdf.set_font("Helvetica", "B", 9)
                    pdf.set_text_color(100, 40, 40)
                    pdf.cell(0, 6, _safe(f"  [{tm[0][:19]}] {tm[1]}:"), new_x="LMARGIN", new_y="NEXT")
                    pdf.set_font("Helvetica", "", 9)
                    pdf.set_text_color(40, 40, 40)
                    content = tm[2] if len(tm[2]) <= 80 else tm[2][:77] + "..."
                    pdf.cell(0, 6, _safe(f'    "{content}"  (score: {tm[3]:.2f})'), new_x="LMARGIN", new_y="NEXT")
        else:
            pdf.body_text("No victims were identified in the analyzed data.")

        # ── interaction network graph ────────────────────────────────────
        pdf.add_page()
        pdf.section_title("5. Interaction Network")
        flagged_interactions = self.db_repo.get_flagged_interactions()
        if flagged_interactions:
            pdf.body_text("The graph below shows directed toxic interactions between users. Arrows point from aggressor to victim.")

            # build and render the graph to a temp image
            G = nx.DiGraph()
            for sender, receiver, score in flagged_interactions:
                if G.has_edge(sender, receiver):
                    G[sender][receiver]['weight'] += 1
                else:
                    G.add_edge(sender, receiver, weight=1)

            fig, ax = plt.subplots(figsize=(8, 5))
            fig.patch.set_facecolor('white')
            ax.set_facecolor('white')
            pos = nx.spring_layout(G, k=1.5, iterations=50, seed=42)

            nx.draw_networkx_nodes(G, pos, ax=ax, node_color='#4a69bd', node_size=700, edgecolors='#2d3436', linewidths=1.5)
            edge_weights = [G[u][v]['weight'] for u, v in G.edges()]
            max_w = max(edge_weights) if edge_weights else 1
            edge_widths = [1 + (w / max_w) * 3 for w in edge_weights]
            nx.draw_networkx_edges(G, pos, ax=ax, arrowstyle='->', arrowsize=20,
                                   edge_color='#e74c3c', width=edge_widths, alpha=0.8,
                                   connectionstyle="arc3,rad=0.1")
            nx.draw_networkx_labels(G, pos, ax=ax, font_size=9, font_weight='bold', font_color='white')
            ax.axis('off')
            plt.tight_layout()

            # Save to temp file and embed in PDF
            import tempfile
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
            fig.savefig(tmp.name, dpi=150, bbox_inches='tight', facecolor='white')
            plt.close(fig)
            tmp.close()

            pdf.image(tmp.name, x=15, w=180)
            os.unlink(tmp.name)
        else:
            pdf.body_text("No flagged interactions were found to generate a network graph.")

        # ── recommendations ──────────────────────────────────────────────
        pdf.add_page()
        pdf.section_title("6. Recommendations")
        recommendations = []
        if stats['critical_alerts'] > 0:
            recommendations.append("URGENT: Review all CRITICAL alerts immediately. These may involve threats of violence or coordinated harassment.")
        if victims:
            top_v = victims[0]
            if top_v[3] >= 2:
                recommendations.append(f"GANG-UP DETECTED: {top_v[1]} is being targeted by {top_v[3]} distinct aggressors. Consider separating the victim from the group.")
            recommendations.append(f"PRIMARY VICTIM: {top_v[1]} has been targeted {top_v[2]} times. Monitor their wellbeing and provide support.")
        if top_users:
            recommendations.append(f"TOP OFFENDER: {top_users[0][1]} has the highest risk score ({top_users[0][2]:.2f}). Consider restricting their messaging privileges.")
        if not recommendations:
            recommendations.append("No immediate actions required. Continue routine monitoring.")

        for i, rec in enumerate(recommendations, 1):
            pdf.set_font("Helvetica", "B" if "URGENT" in rec else "", 10)
            pdf.set_text_color(200, 0, 0) if "URGENT" in rec else pdf.set_text_color(40, 40, 40)
            pdf.multi_cell(0, 6, _safe(f"{i}. {rec}"))
            pdf.ln(3)

        # return as bytes
        return pdf.output()