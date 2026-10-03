"""HTML email template generator for editorial subscriber newsletters."""

from datetime import datetime

def notify_subscriber_template(header: str, news_content: str, user_email: str) -> str:
    """Renders a responsive, text-only HTML briefing designed for high deliverability and clarity."""
    current_date = datetime.now().strftime("%B %d, %Y")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{header}</title>
    <style>
        body {{
            margin: 0;
            padding: 0;
            background-color: #f1f5f9;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            color: #1e293b;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }}
        .wrapper {{
            width: 100%;
            background-color: #f1f5f9;
            padding: 40px 12px;
            box-sizing: border-box;
        }}
        .container {{
            max-width: 660px;
            margin: 0 auto;
            background: #ffffff;
            border-radius: 8px;
            border: 1px solid #e2e8f0;
            overflow: hidden;
            box-shadow: 0 4px 12px rgba(15, 23, 42, 0.05);
        }}
        .masthead {{
            padding: 32px 36px 24px 36px;
            border-bottom: 2px solid #0f172a;
            background: #ffffff;
        }}
        .masthead-meta {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 1.5px;
            text-transform: uppercase;
            color: #64748b;
            margin-bottom: 12px;
        }}
        .masthead-brand {{
            color: #0f172a;
            font-size: 13px;
            letter-spacing: 2px;
            font-weight: 800;
        }}
        .masthead-date {{
            color: #64748b;
        }}
        .masthead h1 {{
            margin: 8px 0 0 0;
            font-size: 26px;
            font-weight: 800;
            line-height: 1.3;
            color: #0f172a;
            letter-spacing: -0.5px;
        }}
        .content {{
            padding: 36px 36px 28px 36px;
            font-size: 16px;
            line-height: 1.75;
            color: #334155;
        }}
        .article-entry {{
            margin-bottom: 36px;
            padding-bottom: 36px;
            border-bottom: 1px solid #e2e8f0;
        }}
        .article-entry:last-child {{
            margin-bottom: 0;
            padding-bottom: 0;
            border-bottom: none;
        }}
        .category-tag {{
            display: inline-block;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #2563eb;
            background: #eff6ff;
            padding: 3px 10px;
            border-radius: 4px;
            margin-bottom: 10px;
        }}
        .article-title {{
            margin: 0 0 14px 0;
            font-size: 22px;
            font-weight: 700;
            color: #0f172a;
            line-height: 1.35;
            letter-spacing: -0.3px;
        }}
        .article-summary {{
            font-size: 16px;
            font-weight: 500;
            color: #475569;
            margin: 0 0 18px 0;
            line-height: 1.7;
        }}
        .article-body {{
            font-size: 15px;
            color: #334155;
            line-height: 1.8;
        }}
        .article-body h3 {{
            margin: 22px 0 10px 0;
            font-size: 16px;
            font-weight: 700;
            color: #0f172a;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .article-body p {{
            margin: 0 0 16px 0;
        }}
        .article-body ul {{
            margin: 0 0 18px 0;
            padding-left: 20px;
        }}
        .article-body li {{
            margin-bottom: 6px;
        }}
        .takeaway-box {{
            margin-top: 18px;
            padding: 14px 18px;
            background: #f8fafc;
            border-left: 3px solid #2563eb;
            border-radius: 0 6px 6px 0;
            font-size: 14px;
            color: #1e293b;
            line-height: 1.6;
        }}
        .takeaway-box strong {{
            color: #0f172a;
        }}
        .editor-note {{
            margin-top: 32px;
            padding: 18px 20px;
            background: #f8fafc;
            border-radius: 6px;
            border: 1px solid #e2e8f0;
            font-size: 13px;
            color: #64748b;
            line-height: 1.6;
        }}
        .footer {{
            background: #0f172a;
            padding: 28px 36px;
            text-align: center;
            font-size: 12px;
            color: #94a3b8;
            line-height: 1.7;
        }}
        .footer strong {{
            color: #e2e8f0;
        }}
        .footer-links {{
            margin-top: 10px;
            font-size: 11px;
            color: #64748b;
        }}
        .footer-links a {{
            color: #94a3b8;
            text-decoration: underline;
            margin: 0 8px;
        }}
        @media only screen and (max-width: 600px) {{
            .wrapper {{
                padding: 16px 8px;
            }}
            .masthead, .content, .footer {{
                padding-left: 20px;
                padding-right: 20px;
            }}
            .masthead h1 {{
                font-size: 22px;
            }}
            .article-title {{
                font-size: 19px;
            }}
        }}
    </style>
</head>
<body>
    <div class="wrapper">
        <div class="container">
            <div class="masthead">
                <div class="masthead-meta">
                    <span class="masthead-brand">LUCIDTREND</span>
                    <span class="masthead-date">{current_date}</span>
                </div>
                <h1>{header}</h1>
            </div>
            <div class="content">
                {news_content}
                <div class="editor-note">
                    <strong>LucidTrend Technical Desk:</strong> This intelligence briefing is distilled directly from primary engineering documentation, release diffs, and benchmark reports.
                </div>
            </div>
            <div class="footer">
                You are receiving this technical intelligence briefing as a verified subscriber.<br>
                Recipient: <strong>{user_email}</strong><br>
                <div class="footer-links">
                    © {datetime.now().year} LucidTrend Systems. All rights reserved.
                </div>
            </div>
        </div>
    </div>
</body>
</html>"""