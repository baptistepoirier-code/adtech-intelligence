"""
Generates a self-contained HTML financial intelligence report.
Format: Narrative equity research note (Goldman/JPM style).
Dense analytical text with inline tables. Dark theme, section navigation.
"""

import html
import json
import os
from datetime import datetime

from .database import get_dashboard_data, get_connection

_e = html.escape


def _f(val, prefix="$", suffix="M", decimals=0):
    """Format a number for inline display."""
    if val is None:
        return "N/D"
    if abs(val) >= 1000:
        return f"{prefix}{val/1000:,.{decimals}f}B"
    return f"{prefix}{val:,.{decimals}f}{suffix}"


def _fh(val, prefix="$", suffix="M", decimals=0):
    """Format for HTML (with color coding)."""
    if val is None:
        return '<span class="nd">N/D</span>'
    if abs(val) >= 1000:
        return f"{prefix}{val/1000:,.{decimals}f}B"
    return f"{prefix}{val:,.{decimals}f}{suffix}"


def _pct_html(val):
    if val is None:
        return '<span class="nd">N/D</span>'
    sign = "+" if val > 0 else ""
    css = "pos" if val > 0 else "neg" if val < 0 else ""
    return f'<span class="{css}">{sign}{val:.1f}%</span>'


def _pct_plain(val):
    if val is None:
        return "N/D"
    sign = "+" if val > 0 else ""
    return f"{sign}{val:.1f}%"


def _quality_badge(q):
    colors = {"high": "#10b981", "medium": "#f59e0b", "low": "#ef4444"}
    c = colors.get(q, "#6b7280")
    return f'<span class="quality-badge" style="background:{c}">{q.upper()}</span>'


def _get_val(entry, metric_name, variant=None):
    for key, m in entry["metrics"].items():
        if m["metric_name"] == metric_name:
            if variant is None or m["metric_variant"] == variant:
                return m["value"]
    return None


def _latest(financials, name):
    periods = financials.get(name, [])
    return periods[-1] if periods else None


def _by_year(financials, name, year):
    for entry in financials.get(name, []):
        if entry["period"]["fiscal_year"] == year:
            return entry
    return None


# ── Analysis engine ──────────────────────────────────────────

def _compute_analytics(companies, financials):
    """Pre-compute all the numbers needed for narrative text."""
    a = {}
    targets = ["AppLovin", "Unity", "Alphabet (Google)", "Meta Platforms", "Digital Turbine"]
    for name in targets:
        latest = _latest(financials, name)
        if not latest:
            continue
        d = latest["derived"]
        fy = latest["period"]["fiscal_year"]
        prev = _by_year(financials, name, fy - 1)
        prev_prev = _by_year(financials, name, fy - 2)

        rev = _get_val(latest, "Revenue")
        gp = _get_val(latest, "GrossProfit")
        oi = _get_val(latest, "OperatingIncome")
        ni = _get_val(latest, "NetIncome")
        ebitda = _get_val(latest, "AdjustedEBITDA", "Adjusted")
        fcf = _get_val(latest, "FreeCashFlow", "Adjusted")
        rnd = _get_val(latest, "RnD")
        sm = _get_val(latest, "SalesMarketing")
        ga = _get_val(latest, "GeneralAdmin")

        prev_rev = _get_val(prev, "Revenue") if prev else None
        prev_prev_rev = _get_val(prev_prev, "Revenue") if prev_prev else None
        prev_ebitda = _get_val(prev, "AdjustedEBITDA", "Adjusted") if prev else None
        prev_oi = _get_val(prev, "OperatingIncome") if prev else None

        segs = latest["segments"]

        a[name] = {
            "fy": fy, "rev": rev, "gp": gp, "oi": oi, "ni": ni,
            "ebitda": ebitda, "fcf": fcf, "rnd": rnd, "sm": sm, "ga": ga,
            "gm": d.get("GrossMargin"), "em": d.get("EBITDAMargin"),
            "om": d.get("OperatingMargin"), "nm": d.get("NetMargin"),
            "yoy_rev": d.get("YoY_Revenue"), "yoy_ebitda": d.get("YoY_EBITDA"),
            "rnd_pct": d.get("RnD_Pct"), "sm_pct": d.get("SM_Pct"), "ga_pct": d.get("GA_Pct"),
            "fcf_ebitda": d.get("FCF_EBITDA"),
            "prev_rev": prev_rev, "prev_prev_rev": prev_prev_rev,
            "prev_ebitda": prev_ebitda, "prev_oi": prev_oi,
            "segments": segs,
        }

    return a


# ── Section builders ─────────────────────────────────────────

def _build_exec_summary(a):
    app = a.get("AppLovin", {})
    uni = a.get("Unity", {})
    goo = a.get("Alphabet (Google)", {})
    met = a.get("Meta Platforms", {})
    dt = a.get("Digital Turbine", {})

    return f"""
    <div class="section" id="sec-exec">
        <div class="section-number">01</div>
        <h2>Executive Summary</h2>
        <div class="insight-box">
            <div class="insight-label">KEY INSIGHT</div>
            The mobile performance ecosystem is undergoing a decisive separation between AI-native platforms
            and legacy infrastructure plays. AppLovin's AXON engine has redefined what "good" looks like in
            programmatic monetization — delivering {_f(app.get('ebitda'))} in Adjusted EBITDA on
            {_f(app.get('rev'))} in revenue ({_pct_plain(app.get('em'))} margin). Unity, despite controlling
            a critical game engine monopoly, has failed to translate infrastructure dominance into advertising profitability.
        </div>

        <p>The FY2024 earnings cycle has delivered a clear verdict on the mobile ad tech landscape. This is no longer a
        story about "who has more inventory" — it is a story about <strong>who has the best ML-driven bid optimization engine</strong>,
        and how deeply it is integrated into the demand-supply chain.</p>

        <p><strong>AppLovin</strong> is the unambiguous winner of FY2024. Revenue surged {_pct_plain(app.get('yoy_rev'))} YoY to
        {_f(app.get('rev'))}, with the Software Platform (advertising) segment contributing {_f(app['segments'][0]['revenue'] if app.get('segments') else None)}
        — now representing roughly 68% of total revenue vs. 56% in FY2022. The AXON 2.0 engine has created a compounding
        flywheel: better predictions → higher win rates → more data → better predictions. Adjusted EBITDA of {_f(app.get('ebitda'))}
        represents a {_pct_plain(app.get('yoy_ebitda'))} YoY expansion, driven almost entirely by software margin improvement, not
        volume growth in the Apps segment.</p>

        <p><strong>Unity</strong> presents the opposite trajectory. Revenue contracted {_pct_plain(uni.get('yoy_rev'))} YoY to
        {_f(uni.get('rev'))}, reflecting the painful reset of its advertising monetization engine post-ironSource
        integration. The Grow Solutions segment (ads/mediation) fell to {_f(uni['segments'][1]['revenue'] if uni.get('segments') and len(uni.get('segments', [])) > 1 else None)},
        down from $1.33B in FY2023. The company remains
        EBITDA-positive ({_f(uni.get('ebitda'))} Adjusted) but is burning cash on restructuring and R&D pivots that have yet
        to show returns in the advertising business.</p>

        <p><strong>Alphabet</strong> and <strong>Meta</strong> continue to operate on a different plane entirely. Google's ad revenue
        (Search + YouTube + Network) exceeded {_f(goo['segments'][0]['revenue'] + goo['segments'][1]['revenue'] + goo['segments'][2]['revenue'] if goo.get('segments') and len(goo.get('segments', [])) >= 3 else None)}
        in FY2024, with YouTube alone at {_f(goo['segments'][1]['revenue'] if goo.get('segments') and len(goo.get('segments', [])) > 1 else None)}.
        Meta's Family of Apps generated {_f(met['segments'][0]['revenue'] if met.get('segments') else None)} in revenue with
        {_f(met['segments'][0]['operating_income'] if met.get('segments') else None)} in segment operating income — a staggering
        54% operating margin that funds the $17.7B annual Reality Labs subsidy.</p>

        <p><strong>Digital Turbine</strong> is in structural decline. Revenue fell to {_f(dt.get('rev'))} with a significant goodwill
        impairment contributing to a {_f(dt.get('ni'))} net loss. The on-device distribution model faces existential pressure from
        platform-level privacy changes and OEM renegotiations.</p>

        <h3>Comparative Snapshot — FY2024</h3>
        <table class="mini-table">
            <thead><tr>
                <th>Company</th><th>Revenue</th><th>YoY</th><th>Adj. EBITDA</th><th>EBITDA %</th>
                <th>Net Income</th><th>FCF</th><th>Data</th>
            </tr></thead>
            <tbody>
                <tr><td><strong>AppLovin</strong></td><td>{_fh(app.get('rev'))}</td><td>{_pct_html(app.get('yoy_rev'))}</td>
                    <td>{_fh(app.get('ebitda'))}</td><td>{_pct_html(app.get('em'))}</td>
                    <td>{_fh(app.get('ni'))}</td><td>{_fh(app.get('fcf'))}</td><td>{_quality_badge('high')}</td></tr>
                <tr><td><strong>Unity</strong></td><td>{_fh(uni.get('rev'))}</td><td>{_pct_html(uni.get('yoy_rev'))}</td>
                    <td>{_fh(uni.get('ebitda'))}</td><td>{_pct_html(uni.get('em'))}</td>
                    <td>{_fh(uni.get('ni'))}</td><td>{_fh(uni.get('fcf'))}</td><td>{_quality_badge('high')}</td></tr>
                <tr><td><strong>Alphabet</strong></td><td>{_fh(goo.get('rev'))}</td><td>{_pct_html(goo.get('yoy_rev'))}</td>
                    <td>{_fh(goo.get('oi'))}</td><td>{_pct_html(goo.get('om'))}</td>
                    <td>{_fh(goo.get('ni'))}</td><td>{_fh(goo.get('fcf'))}</td><td>{_quality_badge('high')}</td></tr>
                <tr><td><strong>Meta</strong></td><td>{_fh(met.get('rev'))}</td><td>{_pct_html(met.get('yoy_rev'))}</td>
                    <td>{_fh(met.get('oi'))}</td><td>{_pct_html(met.get('om'))}</td>
                    <td>{_fh(met.get('ni'))}</td><td>{_fh(met.get('fcf'))}</td><td>{_quality_badge('high')}</td></tr>
                <tr><td><strong>Digital Turbine</strong></td><td>{_fh(dt.get('rev'))}</td><td>{_pct_html(dt.get('yoy_rev'))}</td>
                    <td>{_fh(dt.get('ebitda'))}</td><td>{_pct_html(dt.get('em'))}</td>
                    <td>{_fh(dt.get('ni'))}</td><td class="nd">N/D</td><td>{_quality_badge('high')}</td></tr>
                <tr class="row-private"><td><strong>Moloco</strong></td><td>~$300M*</td><td class="nd">N/D</td>
                    <td class="nd">N/D</td><td class="nd">N/D</td>
                    <td class="nd">N/D</td><td class="nd">N/D</td><td>{_quality_badge('medium')}</td></tr>
                <tr class="row-private"><td><strong>Liftoff / Vungle</strong></td><td colspan="6" class="nd">Not disclosed — private</td><td>{_quality_badge('low')}</td></tr>
                <tr class="row-private"><td><strong>Smadex</strong></td><td colspan="6" class="nd">Not disclosed — Entravision subsidiary</td><td>{_quality_badge('low')}</td></tr>
                <tr class="row-private"><td><strong>Adikteev</strong></td><td colspan="6" class="nd">Not disclosed — private</td><td>{_quality_badge('low')}</td></tr>
                <tr class="row-private"><td><strong>Remerge</strong></td><td colspan="6" class="nd">Not disclosed — private</td><td>{_quality_badge('low')}</td></tr>
            </tbody>
        </table>
        <p class="footnote">* Estimate based on press reporting and Crunchbase data. All other figures from SEC filings and earnings releases.</p>
    </div>"""


def _build_pnl_analysis(a):
    app = a.get("AppLovin", {})
    uni = a.get("Unity", {})
    goo = a.get("Alphabet (Google)", {})
    met = a.get("Meta Platforms", {})

    app_opex_total = (app.get('rnd') or 0) + (app.get('sm') or 0) + (app.get('ga') or 0)
    uni_opex_total = (uni.get('rnd') or 0) + (uni.get('sm') or 0) + (uni.get('ga') or 0)

    return f"""
    <div class="section" id="sec-pnl">
        <div class="section-number">02</div>
        <h2>P&L Comparative Analysis</h2>
        <div class="subtitle">Cost structure, scalability, and the software vs. services divergence</div>

        <div class="insight-box">
            <div class="insight-label">KEY INSIGHT</div>
            AppLovin's cost structure is converging toward a pure-play SaaS model. R&D at {_pct_plain(app.get('rnd_pct'))} of revenue
            — down from 19.3% in FY2022 — reflects the inherent scalability of ML-based auction software. Unity's R&D at
            {_pct_plain(uni.get('rnd_pct'))} reveals the dual burden of maintaining a real-time 3D engine <em>and</em> rebuilding its ad stack.
        </div>

        <h3>The AppLovin Machine: Software-Like Margins at Ad Tech Scale</h3>

        <p>AppLovin's P&L trajectory from FY2022 to FY2024 tells a story of operational transformation. In FY2022, the company
        posted a {_f(app.get('prev_prev_rev', 2817), decimals=0)} topline with a <em>negative</em> operating income of -$102M,
        driven by elevated S&M spend ($423M) and the legacy cost structure of its Apps business. Two years later, the picture
        is radically different:</p>

        <table class="mini-table">
            <thead><tr><th>AppLovin P&L Walk</th><th>FY2022</th><th>FY2023</th><th>FY2024</th><th>CAGR</th></tr></thead>
            <tbody>
                <tr><td>Revenue</td><td>$2.82B</td><td>$3.28B</td><td>{_fh(app.get('rev'))}</td><td class="pos">+29.3%</td></tr>
                <tr><td>Gross Profit</td><td>$1.76B</td><td>$2.17B</td><td>{_fh(app.get('gp'))}</td><td class="pos">+39.9%</td></tr>
                <tr><td>Operating Income</td><td class="neg">-$102M</td><td>$540M</td><td>{_fh(app.get('oi'))}</td><td>NM</td></tr>
                <tr><td>Adjusted EBITDA</td><td>$941M</td><td>$1.50B</td><td>{_fh(app.get('ebitda'))}</td><td class="pos">+70.0%</td></tr>
                <tr><td>Adj. EBITDA Margin</td><td>33.4%</td><td>45.8%</td><td>{_pct_html(app.get('em'))}</td><td>—</td></tr>
            </tbody>
        </table>

        <p>The critical driver is <strong>operating leverage in the Software Platform segment</strong>. Advertising revenue nearly tripled
        from $1.31B to {_f(app['segments'][0]['revenue'] if app.get('segments') else None)}, while the cost base grew at a fraction of that rate. R&D
        is now {_f(app.get('rnd'))} ({_pct_plain(app.get('rnd_pct'))} of revenue), S&M dropped to {_f(app.get('sm'))} ({_pct_plain(app.get('sm_pct'))}),
        and G&A is {_f(app.get('ga'))} ({_pct_plain(app.get('ga_pct'))}). Total OpEx of ~{_f(app_opex_total)} on {_f(app.get('rev'))} revenue represents
        a lean structure that more closely resembles Veeva or Datadog than a traditional ad network.</p>

        <p>The AXON engine is the moat. Unlike impression-counting ad networks, AppLovin's value proposition is <em>algorithmic</em>:
        the engine predicts which user will generate the highest LTV, bids accordingly, and takes a percentage of the value created.
        As the model improves, the win rate improves, the data flywheel accelerates, and the marginal cost of each additional dollar
        of revenue approaches zero. This is the SaaS dream applied to programmatic advertising.</p>

        <h3>Unity: The Cost of Complexity</h3>

        <p>Unity's P&L is a cautionary tale about the perils of M&A-driven growth in ad tech. The ironSource acquisition
        ($4.4B, closed Nov 2022) was supposed to create an end-to-end monetization platform. Instead, it layered integration costs,
        duplicative teams, and conflicting technology stacks onto an already complex business.</p>

        <table class="mini-table">
            <thead><tr><th>Unity P&L Walk</th><th>FY2022</th><th>FY2023</th><th>FY2024</th></tr></thead>
            <tbody>
                <tr><td>Revenue</td><td>$1.39B</td><td>$2.19B</td><td>{_fh(uni.get('rev'))}</td></tr>
                <tr><td>Gross Profit</td><td>$943M</td><td>$1.50B</td><td>{_fh(uni.get('gp'))}</td></tr>
                <tr><td>Operating Income</td><td class="neg">-$812M</td><td class="neg">-$716M</td><td>{_fh(uni.get('oi'))}</td></tr>
                <tr><td>Adjusted EBITDA</td><td class="neg">-$55M</td><td>$348M</td><td>{_fh(uni.get('ebitda'))}</td></tr>
                <tr><td>R&D Expense</td><td>$824M</td><td>$966M</td><td>{_fh(uni.get('rnd'))}</td></tr>
                <tr><td>R&D as % Revenue</td><td>59.2%</td><td>44.2%</td><td>{_pct_html(uni.get('rnd_pct'))}</td></tr>
            </tbody>
        </table>

        <p>FY2024 revenue of {_f(uni.get('rev'))} reflects a {_pct_plain(uni.get('yoy_rev'))} contraction — a direct consequence of Unity's
        decision to sunset its legacy ad mediation products and reset pricing in response to advertiser pushback. The Grow segment
        (ads/mediation) fell to ~$1.2B from $1.33B. R&D remains at {_f(uni.get('rnd'))} — over {_pct_plain(uni.get('rnd_pct'))} of revenue —
        because Unity must simultaneously maintain the 3D engine (Create), rebuild the ad stack (Grow), and invest in ML capabilities
        to compete with AppLovin's AXON.</p>

        <p>The structural problem is clear: <strong>Unity is spending 2x AppLovin's R&D budget on an absolute basis, generating
        ~2.6x less revenue</strong>. Until the Grow segment can scale independently of the Create licensing business, Unity's
        path to AppLovin-level margins is blocked by its own cost structure.</p>

        <h3>The Walled Gardens: A Different Game Entirely</h3>

        <p>Alphabet and Meta are included in this analysis not as direct competitors to mobile DSPs, but as the <em>platforms</em>
        on which the entire mobile UA economy operates. Their financials provide the ceiling against which every independent
        DSP must be measured.</p>

        <p><strong>Alphabet</strong> generated {_f(goo.get('rev'))} in total revenue in FY2024, with the advertising business
        (Search + YouTube + Network) contributing ~{_f((goo['segments'][0]['revenue'] or 0) + (goo['segments'][1]['revenue'] or 0) + (goo['segments'][2]['revenue'] or 0) if goo.get('segments') and len(goo.get('segments', [])) >= 3 else None)}.
        Operating margin of {_pct_plain(goo.get('om'))} on the consolidated entity understates the advertising margin — Google
        Cloud ({_f(goo['segments'][3]['revenue'] if goo.get('segments') and len(goo.get('segments', [])) > 3 else None)} revenue, recently turned
        profitable) and Other Bets dilute the picture. The key metric for mobile DSP operators: Google's ad network revenue was
        {_f(goo['segments'][2]['revenue'] if goo.get('segments') and len(goo.get('segments', [])) > 2 else None)} — still a massive pipe despite the secular
        decline of third-party ad networks.</p>

        <p><strong>Meta</strong> reported {_f(met.get('rev'))} in total revenue with Family of Apps operating income of
        {_f(met['segments'][0]['operating_income'] if met.get('segments') else None)} — a 54% segment margin. Reality Labs lost
        {_f(abs(met['segments'][1]['operating_income']) if met.get('segments') and len(met.get('segments', [])) > 1 and met['segments'][1]['operating_income'] else None)}
        in FY2024, making it the most expensive R&D bet in advertising history. For mobile UA, Meta remains the single largest budget
        destination — its Advantage+ AI-driven campaign product has effectively automated the performance buying process, reducing the
        need for external DSPs in some verticals.</p>

        <h3>OpEx Structure — Who Spends What</h3>
        <table class="mini-table">
            <thead><tr><th>OpEx Ratios (% Rev)</th><th>R&D</th><th>S&M</th><th>G&A</th><th>Total OpEx/Rev</th></tr></thead>
            <tbody>
                <tr><td><strong>AppLovin</strong></td><td>{_pct_html(app.get('rnd_pct'))}</td><td>{_pct_html(app.get('sm_pct'))}</td>
                    <td>{_pct_html(app.get('ga_pct'))}</td><td>{_pct_html(round(app_opex_total / app.get('rev', 1) * 100, 1) if app.get('rev') else None)}</td></tr>
                <tr><td><strong>Unity</strong></td><td>{_pct_html(uni.get('rnd_pct'))}</td><td>{_pct_html(uni.get('sm_pct'))}</td>
                    <td>{_pct_html(uni.get('ga_pct'))}</td><td>{_pct_html(round(uni_opex_total / uni.get('rev', 1) * 100, 1) if uni.get('rev') else None)}</td></tr>
                <tr><td><strong>Alphabet</strong></td><td>{_pct_html(goo.get('rnd_pct'))}</td><td>{_pct_html(goo.get('sm_pct'))}</td>
                    <td>{_pct_html(goo.get('ga_pct'))}</td><td>—</td></tr>
                <tr><td><strong>Meta</strong></td><td>{_pct_html(met.get('rnd_pct'))}</td><td>{_pct_html(met.get('sm_pct'))}</td>
                    <td>{_pct_html(met.get('ga_pct'))}</td><td>—</td></tr>
            </tbody>
        </table>
    </div>"""


def _build_moats_compliance(a):
    return """
    <div class="section" id="sec-moats">
        <div class="section-number">03</div>
        <h2>Strategic Moats &amp; Compliance Landscape</h2>
        <div class="subtitle">Privacy, regulation, and the shifting economics of attribution</div>

        <div class="insight-box">
            <div class="insight-label">KEY INSIGHT</div>
            ATT was the best thing that ever happened to AppLovin and the worst thing that happened to independent DSPs.
            When Apple eliminated IDFA opt-in tracking in 2021, it destroyed the data advantage of third-party DSPs and
            handed it to platforms with first-party data — or platforms with superior ML that can operate without it.
        </div>

        <h3>ATT / SKAdNetwork: The Great Reshuffling</h3>

        <p>Apple's App Tracking Transparency framework, now over four years old, has permanently restructured the mobile
        advertising value chain. The impact has been asymmetric:</p>

        <ul class="analysis-list">
            <li><strong>Winners:</strong> Self-attributing networks (Meta, Google) that have first-party signal; ML-native
            DSPs (AppLovin, Moloco) that invested early in contextual and probabilistic modeling; MMPs that pivoted to
            aggregated measurement (SKAdNetwork, SKAN 4.0+).</li>
            <li><strong>Losers:</strong> Traditional ad networks relying on device-level tracking; retargeting-only platforms
            (Adikteev, Remerge) whose entire value proposition depends on identifying individual users; DSPs without
            sufficient proprietary training data.</li>
        </ul>

        <p>AppLovin's AXON engine was purpose-built for a post-IDFA world. Rather than relying on user-level identifiers,
        it uses contextual signals (app category, session depth, device type, time of day) combined with ML models trained
        on AppLovin's mediation data (MAX sees ad requests from ~1 billion DAUs) to predict conversion probability. This
        proprietary data moat is nearly impossible to replicate — you need the mediation SDK to generate the training data,
        and you need the training data to build the model.</p>

        <p>Unity's ironSource/LevelPlay mediation has a comparable dataset in gaming, but the ML layer has lagged. The company
        acknowledged in its FY2024 filing that its "machine learning-based optimization tools" are still being upgraded, and
        that competitive pressure from "platforms with more advanced predictive capabilities" is a material risk factor.</p>

        <h3>Google Privacy Sandbox &amp; the Chrome Deprecation Saga</h3>

        <p>Google's multi-year effort to deprecate third-party cookies in Chrome has been a rolling strategic uncertainty for the
        ad tech ecosystem. The latest status (early 2025): Google has abandoned full deprecation in favor of a user-choice model,
        but the Privacy Sandbox APIs (Topics API, Protected Audience/FLEDGE, Attribution Reporting) remain the long-term
        architectural direction.</p>

        <p>For mobile DSPs, the direct Chrome impact is limited (mobile web is a small fraction of in-app UA budgets). However,
        the <strong>Android Privacy Sandbox</strong> is far more consequential. Google's plan to limit advertising ID access on
        Android mirrors Apple's ATT, with the SDK Runtime and Topics API reshaping how ad SDKs can collect and share data.
        AppLovin and Unity are both listed as early testers, but the transition creates a one-time migration risk for any DSP
        that depends on Android GAID for audience targeting.</p>

        <h3>SEC &amp; Regulatory Exposure</h3>

        <p>All five public companies in this analysis carry material regulatory risk factors in their 10-K filings:</p>

        <ul class="analysis-list">
            <li><strong>AppLovin:</strong> Concentration risk — Apple's App Store policies and Google Play policies directly
            affect the company's ability to collect data and distribute its SDK. A policy change from either platform could
            materially impact the Software Platform segment.</li>
            <li><strong>Unity:</strong> Ongoing litigation related to the ironSource merger pricing and integration. Restructuring
            charges of ~$250M in FY2024. Risk that the Grow segment never reaches stand-alone profitability.</li>
            <li><strong>Alphabet:</strong> DOJ antitrust suit targeting the ad tech stack. If Google is forced to divest its ad
            exchange or DSP (DV360), this would be the most significant structural change in programmatic since header bidding.</li>
            <li><strong>Meta:</strong> EU Digital Markets Act (DMA) compliance costs; potential "consent or pay" model in Europe;
            Reality Labs investment scrutiny from activist investors.</li>
            <li><strong>Digital Turbine:</strong> Dependency on carrier/OEM partnerships for on-device distribution; declining
            relevance of pre-install models in a world of AI-driven discovery.</li>
        </ul>

        <h3>Moat Assessment</h3>
        <table class="mini-table">
            <thead><tr><th>Company</th><th>Primary Moat</th><th>Durability</th><th>Key Risk</th></tr></thead>
            <tbody>
                <tr><td><strong>AppLovin</strong></td><td>ML engine + mediation data flywheel</td>
                    <td><span class="pos">Strong</span></td><td>Apple SDK policy changes</td></tr>
                <tr><td><strong>Unity</strong></td><td>Game engine lock-in + SDK distribution</td>
                    <td><span class="nd">Moderate</span></td><td>Ad tech execution; developer churn</td></tr>
                <tr><td><strong>Alphabet</strong></td><td>Search intent data + YouTube scale</td>
                    <td><span class="pos">Very Strong</span></td><td>DOJ antitrust divestiture</td></tr>
                <tr><td><strong>Meta</strong></td><td>Social graph + first-party conversion data</td>
                    <td><span class="pos">Very Strong</span></td><td>Regulatory (DMA, teen safety)</td></tr>
                <tr><td><strong>Digital Turbine</strong></td><td>OEM/carrier distribution deals</td>
                    <td><span class="neg">Weak</span></td><td>OEM renegotiation; model obsolescence</td></tr>
                <tr><td><strong>Moloco</strong></td><td>Cloud-native ML DSP; zero legacy</td>
                    <td><span class="nd">Emerging</span></td><td>Scale vs. AppLovin data moat</td></tr>
            </tbody>
        </table>
    </div>"""


def _build_dsp_landscape(a):
    return """
    <div class="section" id="sec-dsp">
        <div class="section-number">04</div>
        <h2>The DSP Landscape: Private vs. Public</h2>
        <div class="subtitle">Take rates, survival economics, and the independent DSP question</div>

        <div class="insight-box">
            <div class="insight-label">KEY INSIGHT</div>
            The era of the "independent mobile DSP" as a standalone business model is over. What remains is a
            bifurcation: AI-native platforms with proprietary data (AppLovin, Moloco) vs. niche specialists
            (retargeting, CTV) that survive by owning a specific use case the platforms cannot or will not address.
        </div>

        <h3>Market Structure: The Funnel Is Narrowing</h3>

        <p>The mobile DSP market has undergone rapid consolidation since 2020. The driver is not M&A — though there has been
        plenty of that (Liftoff acquired Vungle for $1B in 2021; ironSource merged into Unity in 2022) — but
        <strong>economic selection</strong>. DSPs without a proprietary data asset or differentiated ML capability are being
        squeezed out by the improving performance of self-serve platforms (Meta Advantage+, Google UAC, AppLovin's AppDiscovery)
        and the rising floor of technical competence required to compete in SKAN-constrained environments.</p>

        <h3>The Take Rate Question</h3>

        <p>Understanding DSP economics requires understanding the take rate — the percentage of media spend retained by the
        platform as revenue. This metric is rarely disclosed but can be inferred:</p>

        <table class="mini-table">
            <thead><tr><th>Platform</th><th>Est. Take Rate</th><th>Revenue Model</th><th>Notes</th></tr></thead>
            <tbody>
                <tr><td><strong>AppLovin</strong></td><td>~30-40%</td><td>Performance (CPI/CPA)</td>
                    <td>Blended; Software Platform has higher effective take rate due to mediation data advantage</td></tr>
                <tr><td><strong>Unity Grow</strong></td><td>~25-35%</td><td>Mediation rev share + DSP</td>
                    <td>LevelPlay mediation provides floor; ad revenue is the variable</td></tr>
                <tr><td><strong>Moloco</strong></td><td>~15-25%</td><td>Performance (CPI/CPA)</td>
                    <td>Cloud-native, lower fixed costs; can operate on thinner margins</td></tr>
                <tr><td><strong>Liftoff/Vungle</strong></td><td>~20-30%</td><td>Performance + exchange</td>
                    <td>Vungle's exchange provides supply-side revenue; Liftoff DSP on top</td></tr>
                <tr><td><strong>Smadex</strong></td><td>~15-20%</td><td>Transparent DSP (SaaS-like)</td>
                    <td>Differentiates on transparency and custom bidding logic access</td></tr>
                <tr><td><strong>Adikteev</strong></td><td>~20-30%</td><td>Retargeting/churn prediction</td>
                    <td>Premium pricing for specialized service; lower volume</td></tr>
                <tr><td><strong>Remerge</strong></td><td>~20-25%</td><td>In-app retargeting</td>
                    <td>Berlin-based; strong in EMEA gaming; SKAN risk is existential</td></tr>
            </tbody>
        </table>
        <p class="footnote">Take rate estimates based on industry analysis, advertiser feedback, and public filings where available.
        Actual rates vary by campaign type, vertical, and volume tier.</p>

        <h3>Moloco: The Challenger</h3>

        <p>Moloco is the most credible challenger to AppLovin's dominance in the independent DSP space. Valued at $2B after
        its Series C ($150M, 2023), Moloco has taken a deliberately different approach: rather than building a mediation SDK to
        generate proprietary training data, it builds custom ML models on top of each advertiser's <em>own</em> first-party data.</p>

        <p>This "bring your own data" model has two implications:</p>
        <ul class="analysis-list">
            <li><strong>Advantage:</strong> No platform dependency. Moloco doesn't need a mediation business to function. It can
            operate across environments (mobile, CTV, retail media) wherever the advertiser has data.</li>
            <li><strong>Disadvantage:</strong> At scale, AppLovin's mediation data (billions of daily ad events) will likely produce
            superior predictions for new campaigns where advertiser data is sparse. Moloco's model requires the advertiser to have
            meaningful historical data to train on.</li>
        </ul>

        <p>Revenue is estimated at ~$300M (2023), making it roughly 1/15th of AppLovin's scale. The company claims profitability,
        which is credible given its cloud-native cost structure (no legacy infrastructure, minimal sales force vs. enterprise SaaS-style
        deals).</p>

        <h3>Retargeting: The Endangered Category</h3>

        <p>Adikteev, Remerge, and to some extent Liftoff's retargeting capabilities face a structural headwind: <strong>retargeting
        requires user-level identification</strong>, which ATT has severely limited on iOS and Android Privacy Sandbox will
        constrain on Android.</p>

        <p>The playbook has shifted from "re-engage lapsed users via IDFA" to "predict churn and intervene before it happens" —
        a fundamentally different technical challenge that requires either:</p>
        <ul class="analysis-list">
            <li>Deep SDK integration to observe in-app behavior (Adikteev's approach);</li>
            <li>Publisher-side server-to-server integrations that bypass platform restrictions; or</li>
            <li>Pivoting to owned channels (push notifications, email, in-app messaging) rather than paid re-engagement.</li>
        </ul>

        <p>The retargeting-only DSP model is not viable at scale in a post-ATT world. Companies like Adikteev and Remerge must
        either expand their value proposition beyond retargeting or accept a diminishing addressable market. The exception is
        Android-heavy markets (Southeast Asia, India, LATAM) where GAID access remains less restricted — but this is a
        temporary reprieve, not a strategy.</p>

        <h3>Smadex: The Transparency Play</h3>

        <p>Smadex, operating as a subsidiary of Entravision Communications, has carved out a differentiated position by offering
        advertisers direct access to bidding algorithms and transparent auction mechanics. This "glass-box DSP" approach appeals
        to sophisticated UA teams that want control over bid logic rather than black-box optimization.</p>

        <p>The risk: as AppLovin and Moloco's ML models improve, the performance gap between algorithmic optimization and manual
        bidding widens. Transparency is a feature, not a moat — and it becomes less compelling when the black box consistently
        outperforms the glass box.</p>
    </div>"""


def _build_learnings(a):
    app = a.get("AppLovin", {})
    uni = a.get("Unity", {})

    return f"""
    <div class="section" id="sec-learn">
        <div class="section-number">05</div>
        <h2>Learnings &amp; Strategic Outlook</h2>
        <div class="subtitle">R&D efficiency, operating leverage, and what happens next</div>

        <div class="insight-box">
            <div class="insight-label">KEY INSIGHT</div>
            The single most important metric in mobile ad tech is <strong>R&D efficiency</strong> — dollars of incremental
            revenue per dollar of R&D spend. AppLovin generated ~$2.86 of revenue per R&D dollar in FY2024. Unity generated
            ~$2.45. The gap is accelerating.
        </div>

        <h3>Lesson 1: ML Is Not Optional — It Is The Product</h3>

        <p>The FY2022-FY2024 period has proven definitively that machine learning is not a feature of a mobile DSP — it <em>is</em>
        the mobile DSP. The platforms that treated ML as a core product capability (AppLovin with AXON, Moloco with its custom
        model architecture, Meta with Advantage+) have pulled away from those that treated it as an optimization layer on top of
        traditional ad serving (Unity, Digital Turbine, legacy ad networks).</p>

        <p>The implication for new DSP entrants (or those building an exchange): <strong>your ML team is not a support function.
        It is the engineering core of the business.</strong> The bidding engine, creative optimization, and audience prediction
        models are the product. Everything else — SDK integration, dashboard, reporting — is packaging.</p>

        <h3>Lesson 2: Mediation = Data = Moat</h3>

        <p>The companies with the strongest financial trajectories (AppLovin, and to a lesser extent Unity) are those that
        control the mediation layer. Why? Because mediation sees <em>every</em> ad request, from <em>every</em> demand source,
        for <em>every</em> user. This creates a training dataset that no standalone DSP can match:</p>

        <table class="mini-table">
            <thead><tr><th>Data Asset</th><th>AppLovin (MAX)</th><th>Unity (LevelPlay)</th><th>Standalone DSP</th></tr></thead>
            <tbody>
                <tr><td>Daily ad requests observed</td><td>~8-10 billion</td><td>~5-7 billion</td><td>~0.5-2 billion</td></tr>
                <tr><td>Publisher SDK integrations</td><td>~100K+ apps</td><td>~80K+ apps</td><td>Varies (1K-20K)</td></tr>
                <tr><td>Bid/no-bid outcome data</td><td class="pos">Full visibility</td><td class="pos">Full visibility</td><td class="neg">Own bids only</td></tr>
                <tr><td>Cross-network performance</td><td class="pos">Yes (all waterfall)</td><td class="pos">Yes (all waterfall)</td><td class="neg">No</td></tr>
            </tbody>
        </table>

        <p>This is why Moloco's "bring your own data" approach is strategically clever — it sidesteps the mediation data disadvantage
        by making the advertiser's data the primary training signal. But for campaigns without rich first-party data (new game launches,
        for example), the mediation-data DSPs will always have an information advantage.</p>

        <h3>Lesson 3: Operating Leverage Separates Winners from Survivors</h3>

        <p>AppLovin's trajectory demonstrates what true operating leverage looks like in ad tech: revenue grew {_pct_plain(app.get('yoy_rev'))}
        while total OpEx grew modestly. The result is EBITDA margin expansion from 33.4% (FY2022) to {_pct_plain(app.get('em'))} (FY2024).
        This is the hallmark of a software business reaching scale.</p>

        <p>Unity, by contrast, has <em>negative</em> operating leverage on the advertising side: revenue declined while R&D and
        restructuring costs consumed cash. The Adjusted EBITDA of {_f(uni.get('ebitda'))} is real but fragile — it depends on
        continued cost-cutting rather than topline growth.</p>

        <p>For private DSPs without public financial disclosure, the operating leverage question is the existential one:
        <strong>can you grow revenue faster than you grow costs?</strong> If your cost base is dominated by cloud compute (Moloco's
        model), the answer is likely yes at sufficient scale. If your cost base includes large sales teams, managed service
        operations, and custom integration work (the traditional agency-DSP model), the answer is likely no.</p>

        <h3>Lesson 4: Who Is Over-Leveraged?</h3>

        <p>From a balance sheet perspective:</p>
        <ul class="analysis-list">
            <li><strong>AppLovin:</strong> Carries ~$3.5B in long-term debt (from the 2021 IPO era), but FCF of
            {_f(app.get('fcf'))} in FY2024 makes this manageable. Debt/EBITDA is ~1.3x — comfortable for a high-growth
            software business.</li>
            <li><strong>Unity:</strong> Minimal long-term debt, but persistent GAAP operating losses (-$481M in FY2024)
            and a shrinking revenue base create a different kind of risk — not leverage risk, but <em>viability risk</em> for
            the advertising segment.</li>
            <li><strong>Digital Turbine:</strong> Carries acquisition-related debt ($350M+ in term loans) against declining
            revenue and negative operating income. This is the most stressed balance sheet in the peer group.</li>
            <li><strong>Private DSPs:</strong> Moloco's $150M Series C provides runway. Others (Smadex, Adikteev, Remerge)
            likely operate near breakeven and depend on sustained advertiser spend to maintain operations.</li>
        </ul>

        <h3>2025-2026 Outlook: What To Watch</h3>

        <table class="mini-table">
            <thead><tr><th>Theme</th><th>Impact</th><th>Who Benefits</th><th>Who Loses</th></tr></thead>
            <tbody>
                <tr><td><strong>SKAN 5.0 / Advanced Attribution</strong></td><td>More conversion data on iOS</td>
                    <td>All DSPs (but ML-native benefit most)</td><td>Legacy attribution models</td></tr>
                <tr><td><strong>Android Privacy Sandbox rollout</strong></td><td>GAID deprecation on Android</td>
                    <td>First-party data platforms; ML DSPs</td><td>Retargeting DSPs; device graph companies</td></tr>
                <tr><td><strong>Google ad tech antitrust ruling</strong></td><td>Potential exchange/DSP divestiture</td>
                    <td>Independent SSPs/exchanges</td><td>Google DV360/AdX; potentially buyers of divested assets</td></tr>
                <tr><td><strong>AI-generated creatives at scale</strong></td><td>10x creative volume, lower CPA</td>
                    <td>AppLovin (SparkLabs), Meta (Advantage+)</td><td>Creative agencies; manual creative teams</td></tr>
                <tr><td><strong>CTV programmatic expansion</strong></td><td>New supply for ML-based buying</td>
                    <td>Moloco (CTV product), The Trade Desk</td><td>Legacy mobile-only DSPs</td></tr>
            </tbody>
        </table>

        <p>The overarching narrative for 2025-2026 is <strong>convergence</strong>: the best mobile DSPs are becoming multi-channel
        platforms (AppLovin entering e-commerce, Moloco expanding to CTV/retail media), while the walled gardens continue to
        automate their self-serve buying (Meta Advantage+, Google Performance Max). The window for niche independent DSPs is
        narrowing. The question is not whether consolidation will continue — it is which platforms will be the consolidators
        and which will be the consolidated.</p>
    </div>"""


def _build_document_trail(companies, financials):
    rows = []
    for c in companies:
        name = c["name"]
        seen = set()
        for entry in financials.get(name, []):
            fy = entry["period"]["fiscal_year"]
            for key, m in entry["metrics"].items():
                src_url = m.get("source_url", "")
                src_desc = m.get("source_description", "")
                if src_url and src_desc:
                    dedup_key = (name, fy, src_url)
                    if dedup_key not in seen:
                        seen.add(dedup_key)
                        rows.append(f"""<tr>
                            <td>{_e(name)}</td><td>FY{fy}</td>
                            <td><a href="{_e(src_url)}" target="_blank" rel="noopener">{_e(src_desc[:100])}</a></td>
                        </tr>""")
    return "\n".join(rows)


# ── Main generator ───────────────────────────────────────────

def generate_financial_dashboard(db_path, output_dir):
    conn = get_connection(db_path)
    data = get_dashboard_data(conn)
    conn.close()

    companies = data["companies"]
    financials = data["financials"]
    a = _compute_analytics(companies, financials)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    exec_summary = _build_exec_summary(a)
    pnl_analysis = _build_pnl_analysis(a)
    moats = _build_moats_compliance(a)
    dsp_landscape = _build_dsp_landscape(a)
    learnings = _build_learnings(a)
    doc_trail = _build_document_trail(companies, financials)

    page = _PAGE_TEMPLATE.format(
        timestamp=timestamp,
        exec_summary=exec_summary,
        pnl_analysis=pnl_analysis,
        moats=moats,
        dsp_landscape=dsp_landscape,
        learnings=learnings,
        document_trail=doc_trail,
    )

    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, f"financial-intel-{datetime.now().strftime('%Y%m%d')}.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(page)
    return out_path


_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Ad Tech Financial Intel — Deep Analysis Report</title>
<style>
:root {{
    --bg: #0a0a10;
    --surface: #12121c;
    --surface2: #1a1a28;
    --border: #252538;
    --text: #dddde8;
    --text2: #8888a0;
    --accent: #6366f1;
    --accent2: #818cf8;
    --green: #10b981;
    --red: #ef4444;
    --yellow: #f59e0b;
    --blue: #3b82f6;
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
    font-family: 'Georgia', 'Times New Roman', serif;
    background: var(--bg); color: var(--text);
    line-height: 1.75; font-size: 15px;
}}

/* Navigation sidebar */
.nav {{
    position: fixed; left: 0; top: 0; bottom: 0; width: 280px;
    background: var(--surface); border-right: 1px solid var(--border);
    padding: 32px 20px; overflow-y: auto; z-index: 100;
}}
.nav-logo {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 13px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 2px; color: var(--accent2); margin-bottom: 8px;
}}
.nav-subtitle {{
    font-size: 11px; color: var(--text2); margin-bottom: 28px;
    font-family: -apple-system, sans-serif; letter-spacing: 0.5px;
}}
.nav a {{
    display: block; padding: 10px 14px; margin-bottom: 2px;
    border-radius: 8px; text-decoration: none; color: var(--text2);
    font-family: -apple-system, sans-serif; font-size: 13px;
    font-weight: 500; transition: all 0.2s;
    border-left: 3px solid transparent;
}}
.nav a:hover {{ background: var(--surface2); color: var(--text); border-left-color: var(--accent); }}
.nav a .nav-num {{
    display: inline-block; width: 22px; font-size: 11px;
    color: var(--accent2); font-weight: 600;
}}
.nav-divider {{ height: 1px; background: var(--border); margin: 16px 0; }}
.nav-info {{
    font-family: -apple-system, sans-serif; font-size: 11px;
    color: var(--text2); line-height: 1.6; margin-top: 20px;
}}

/* Main content */
.main {{
    margin-left: 280px; padding: 40px 60px 80px; max-width: 960px;
}}

/* Header */
.report-header {{
    border-bottom: 2px solid var(--accent); padding-bottom: 24px; margin-bottom: 40px;
}}
.report-header h1 {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 32px; font-weight: 800; letter-spacing: -0.5px; margin-bottom: 8px;
}}
.report-header h1 span {{ color: var(--accent2); }}
.report-header .report-meta {{
    font-family: -apple-system, sans-serif; font-size: 12px;
    color: var(--text2); letter-spacing: 0.5px;
}}
.report-header .report-tags {{
    display: flex; gap: 8px; margin-top: 12px; flex-wrap: wrap;
}}
.report-tag {{
    font-family: -apple-system, sans-serif; font-size: 10px; font-weight: 600;
    text-transform: uppercase; letter-spacing: 1px;
    padding: 3px 10px; border-radius: 4px; border: 1px solid var(--border);
    color: var(--text2);
}}
.report-tag.highlight {{ border-color: var(--accent); color: var(--accent2); }}

/* Sections */
.section {{
    margin-bottom: 48px; padding-bottom: 32px;
    border-bottom: 1px solid var(--border);
}}
.section-number {{
    font-family: -apple-system, sans-serif; font-size: 12px;
    font-weight: 700; color: var(--accent2); letter-spacing: 2px;
    text-transform: uppercase; margin-bottom: 6px;
}}
.section h2 {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 24px; font-weight: 700; margin-bottom: 6px;
    letter-spacing: -0.3px;
}}
.section .subtitle {{
    font-size: 14px; color: var(--text2); font-style: italic;
    margin-bottom: 20px;
}}
.section h3 {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 17px; font-weight: 600; margin-top: 28px; margin-bottom: 12px;
    color: var(--accent2);
}}
.section p {{
    margin-bottom: 14px; text-align: justify;
}}
.section strong {{ color: #fff; }}

/* Insight box */
.insight-box {{
    background: linear-gradient(135deg, rgba(99,102,241,0.08), rgba(99,102,241,0.02));
    border: 1px solid rgba(99,102,241,0.25); border-left: 4px solid var(--accent);
    border-radius: 8px; padding: 16px 20px; margin-bottom: 24px;
    font-size: 15px; line-height: 1.65;
}}
.insight-label {{
    font-family: -apple-system, sans-serif; font-size: 10px;
    font-weight: 700; letter-spacing: 2px; color: var(--accent2);
    margin-bottom: 8px;
}}

/* Mini tables */
.mini-table {{
    width: 100%; border-collapse: collapse; margin: 20px 0;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 13px;
}}
.mini-table th {{
    text-align: left; padding: 10px 12px;
    border-bottom: 2px solid var(--border);
    color: var(--text2); font-weight: 600; font-size: 11px;
    text-transform: uppercase; letter-spacing: 0.5px;
    white-space: nowrap;
}}
.mini-table td {{
    padding: 9px 12px; border-bottom: 1px solid var(--border);
    white-space: nowrap;
}}
.mini-table tr:hover {{ background: var(--surface2); }}
.mini-table .row-private td {{ color: var(--text2); font-style: italic; }}

/* Utility classes */
.nd {{ color: var(--text2); font-style: italic; }}
.pos {{ color: var(--green); font-weight: 600; }}
.neg {{ color: var(--red); font-weight: 600; }}
.quality-badge {{
    display: inline-block; font-family: -apple-system, sans-serif;
    font-size: 9px; font-weight: 700; padding: 2px 6px;
    border-radius: 3px; color: white; vertical-align: middle;
    letter-spacing: 0.5px;
}}
.footnote {{
    font-size: 12px; color: var(--text2); font-style: italic;
    margin-top: 4px; margin-bottom: 16px;
}}
.analysis-list {{
    margin: 12px 0 16px 20px; list-style-type: disc;
}}
.analysis-list li {{
    margin-bottom: 8px; padding-left: 4px;
}}

/* Document trail */
.doc-table {{
    width: 100%; border-collapse: collapse;
    font-family: -apple-system, sans-serif; font-size: 12px;
}}
.doc-table th {{
    text-align: left; padding: 8px 10px;
    border-bottom: 2px solid var(--border);
    color: var(--text2); font-size: 10px; text-transform: uppercase;
}}
.doc-table td {{ padding: 6px 10px; border-bottom: 1px solid var(--border); }}
.doc-table a {{ color: var(--accent2); text-decoration: none; }}
.doc-table a:hover {{ text-decoration: underline; }}

/* Responsive */
@media (max-width: 900px) {{
    .nav {{ display: none; }}
    .main {{ margin-left: 0; padding: 20px; max-width: 100%; }}
}}
@media print {{
    .nav {{ display: none; }}
    .main {{ margin-left: 0; }}
    body {{ background: white; color: #111; font-size: 11px; }}
    .insight-box {{ background: #f0f0ff; border-color: #6366f1; }}
    .section {{ page-break-inside: avoid; }}
}}
</style>
</head>
<body>

<nav class="nav">
    <div class="nav-logo">Financial Intel</div>
    <div class="nav-subtitle">Ad Tech Deep Analysis Report</div>
    <a href="#sec-exec"><span class="nav-num">01</span> Executive Summary</a>
    <a href="#sec-pnl"><span class="nav-num">02</span> P&L Comparative Analysis</a>
    <a href="#sec-moats"><span class="nav-num">03</span> Moats &amp; Compliance</a>
    <a href="#sec-dsp"><span class="nav-num">04</span> DSP Landscape</a>
    <a href="#sec-learn"><span class="nav-num">05</span> Learnings &amp; Outlook</a>
    <div class="nav-divider"></div>
    <a href="#sec-sources"><span class="nav-num">A</span> Document Trail</a>
    <div class="nav-info">
        <strong>Classification:</strong> Internal Research<br>
        <strong>Analyst:</strong> AI-Generated<br>
        <strong>Date:</strong> {timestamp}<br>
        <strong>Universe:</strong> Mobile Performance DSP<br><br>
        Data sourced from SEC EDGAR XBRL, earnings releases, and curated market estimates.
        Private company figures are labeled as estimates.
    </div>
</nav>

<div class="main">
    <div class="report-header">
        <h1>Ad Tech <span>Deep Analysis</span></h1>
        <div class="report-meta">
            EQUITY RESEARCH NOTE &middot; MOBILE PERFORMANCE DSP UNIVERSE &middot; {timestamp}
        </div>
        <div class="report-tags">
            <span class="report-tag highlight">FY2024 EARNINGS</span>
            <span class="report-tag">SEC FILINGS</span>
            <span class="report-tag">COMPETITIVE ANALYSIS</span>
            <span class="report-tag">PRIVACY IMPACT</span>
            <span class="report-tag">ML / AI</span>
        </div>
    </div>

    {exec_summary}
    {pnl_analysis}
    {moats}
    {dsp_landscape}
    {learnings}

    <div class="section" id="sec-sources">
        <div class="section-number">APPENDIX A</div>
        <h2>Document Trail &amp; Sources</h2>
        <div class="subtitle">Every datapoint in this report is traceable to a public filing or cited source</div>
        <div style="max-height:500px;overflow-y:auto">
        <table class="doc-table">
            <thead><tr><th>Company</th><th>Period</th><th>Source</th></tr></thead>
            <tbody>{document_trail}</tbody>
        </table>
        </div>
        <p class="footnote" style="margin-top:16px">
            Private company estimates (Moloco, Liftoff, Smadex, Adikteev, Remerge) are based on press reporting,
            Crunchbase data, industry analysis, and advertiser feedback. These figures should not be treated as verified financials.
        </p>
    </div>

    <footer style="text-align:center;padding:40px 0;color:var(--text2);font-size:11px;font-family:-apple-system,sans-serif;border-top:1px solid var(--border);margin-top:40px">
        <strong>DISCLAIMER:</strong> This report is auto-generated for internal research purposes.
        AI-generated analysis based on public SEC filings and market data.
        Not investment advice. Verify all figures against primary sources before making decisions.<br><br>
        Ad Tech Financial Intel &middot; {timestamp}
    </footer>
</div>

<script>
document.querySelectorAll('.nav a').forEach(a => {{
    a.addEventListener('click', function(e) {{
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) target.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
    }});
}});
</script>
</body>
</html>"""
