"""HTML email template generator for editorial subscriber newsletters."""

from datetime import datetime


def notify_subscriber_template(header_or_articles, news_content: str = "", user_email: str = "", summary_content: str = "") -> str:
    """Renders the classic, authoritative NewsPluk technical newsletter briefing."""
    current_date = datetime.now().strftime("%B %d, %Y")
    current_year = datetime.now().year

    if isinstance(header_or_articles, list):
        articles = header_or_articles
        header = f"NewsPluk Technical Dispatch: {articles[0].get('title', 'Daily Briefing')[:60]}" if articles else "NewsPluk Daily Dispatch"
        blocks = []
        for idx, art in enumerate(articles):
            title = art.get("title", "")
            desc = art.get("description") or art.get("excerpt") or ""
            cat = art.get("category") or "Engineering"
            if isinstance(cat, list):
                cat = cat[0] if cat else "Engineering"
            author = art.get("author") or "NewsPluk Editorial"
            read_time = art.get("read_time") or "2 Min Read"
            post_id = art.get("id") or art.get("slug") or ""
            link = f"https://newspluk.com/#article-{post_id}" if post_id else "https://newspluk.com"

            is_last = (idx == len(articles) - 1)
            divider = "" if is_last else '<div style="border-bottom: 1px solid #e2e8f0; margin: 32px 0;"></div>'

            blocks.append(f"""
                <div class="article-entry" style="margin-bottom: 8px;">
                    <div style="margin-bottom: 10px;">
                        <span class="category-tag" style="display: inline-block; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: #2563eb; background: #eff6ff; padding: 3px 10px; border-radius: 4px; border: 1px solid #dbeafe;">
                            {cat}
                        </span>
                    </div>
                    <h2 class="article-title" style="margin: 0 0 12px 0; font-size: 20px; font-weight: 700; line-height: 1.35; letter-spacing: -0.3px;">
                        <a href="{link}" style="color: #0f172a; text-decoration: none;">{title}</a>
                    </h2>
                    <p class="article-summary" style="font-size: 15px; font-weight: 400; color: #475569; margin: 0 0 14px 0; line-height: 1.65;">
                        {desc}
                    </p>
                    <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px;">
                        <a href="{link}" style="display: inline-block; font-size: 13.5px; font-weight: 700; color: #2563eb; text-decoration: none; letter-spacing: 0.2px;">
                            Read Full Dispatch &rarr;
                        </a>
                        <span style="font-size: 12px; color: #94a3b8; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
                            {author} &bull; {read_time}
                        </span>
                    </div>
                    {divider}
                </div>
            """)
        news_content = "".join(blocks)
    else:
        header = str(header_or_articles)

    summary_section = ""
    if summary_content:
        summary_section = f"""
            <!-- EXECUTIVE DIGEST SECTION -->
            <div style="margin-bottom: 32px; padding: 18px 22px; background: #f8fafc; border-left: 3px solid #2563eb; border-radius: 0 6px 6px 0;">
                <div style="font-size: 11px; font-weight: 700; letter-spacing: 1.2px; text-transform: uppercase; color: #2563eb; margin-bottom: 8px;">
                    Executive Summary
                </div>
                <div style="font-size: 14.5px; line-height: 1.7; color: #1e293b;">
                    {summary_content}
                </div>
            </div>
        """

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
            max-width: 640px;
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
        .content {{
            padding: 36px 36px 28px 36px;
            font-size: 15px;
            line-height: 1.75;
            color: #334155;
        }}
        .editor-note {{
            margin-top: 32px;
            padding: 16px 20px;
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
        @media only screen and (max-width: 600px) {{
            .wrapper {{ padding: 16px 8px !important; }}
            .masthead, .content, .footer {{ padding-left: 20px !important; padding-right: 20px !important; }}
            .masthead h1 {{ font-size: 22px !important; }}
            .article-title {{ font-size: 18px !important; }}
        }}
    </style>
</head>
<body>
    <div class="wrapper">
        <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
            <tr>
                <td align="center">
                    <table class="container" role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 640px; margin: 0 auto; background: #ffffff; border-radius: 8px; border: 1px solid #e2e8f0; overflow: hidden; box-shadow: 0 4px 12px rgba(15, 23, 42, 0.05);">
                        <!-- Masthead -->
                        <tr>
                            <td class="masthead" style="padding: 32px 36px 24px 36px; border-bottom: 2px solid #0f172a; background: #ffffff;">
                                <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
                                    <tr>
                                        <td align="left" style="font-size: 11px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; color: #64748b;">
                                            <span style="color: #0f172a; font-size: 13px; letter-spacing: 2px; font-weight: 800;">NEWSPLUK</span> &bull; THE DISPATCH
                                        </td>
                                        <td align="right" style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase;">
                                            {current_date}
                                        </td>
                                    </tr>
                                </table>
                                <h1 style="margin: 12px 0 0 0; font-size: 24px; font-weight: 800; line-height: 1.3; color: #0f172a; letter-spacing: -0.5px;">
                                    {header}
                                </h1>
                            </td>
                        </tr>

                        <!-- Content -->
                        <tr>
                            <td class="content" style="padding: 36px 36px 28px 36px; font-size: 15px; line-height: 1.75; color: #334155;">
                                {summary_section}
                                {news_content}
                                <div class="editor-note" style="margin-top: 32px; padding: 16px 20px; background: #f8fafc; border-radius: 6px; border: 1px solid #e2e8f0; font-size: 13px; color: #64748b; line-height: 1.6;">
                                    <strong style="color: #0f172a;">NewsPluk Editorial Desk:</strong> This intelligence briefing is distilled directly from primary engineering documentation, release diffs, and benchmark reports.
                                </div>
                            </td>
                        </tr>

                        <!-- Dark Footer -->
                        <tr>
                            <td class="footer" style="background: #0f172a; padding: 28px 36px; text-align: center; font-size: 12px; color: #94a3b8; line-height: 1.7;">
                                You are receiving this technical intelligence briefing as a verified subscriber.<br>
                                Recipient: <strong style="color: #e2e8f0;">{user_email or 'subscriber'}</strong><br>
                                <div style="margin-top: 12px; font-size: 11px; color: #64748b;">
                                    &copy; {current_year} NewsPluk Journal. All editorial rights reserved.<br>
                                    <a href="https://newspluk.com" target="_blank" rel="noopener noreferrer" style="color: #94a3b8; text-decoration: underline; margin: 0 8px;">newspluk.com</a>
                                    &bull;
                                    <a href="mailto:contact@newspluk.com" style="color: #94a3b8; text-decoration: underline; margin: 0 8px;">contact@newspluk.com</a>
                                </div>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </div>
</body>
</html>"""