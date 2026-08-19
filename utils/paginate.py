"""
Paginated console display — shows a list of log lines 20 at a time,
waiting for the user to press Enter (or type 'q') between pages.
"""

PAGE_SIZE = 20


def paginate_actions(actions, page_size: int = PAGE_SIZE, title: str = "Changes"):
    """
    Prints `actions` in pages of `page_size`, prompting for input between pages.
    - Enter (blank) -> show next page
    - 'q' -> stop showing pages (rest are skipped, but already logged to file)
    """
    total = len(actions)
    if total == 0:
        print(f"\n{title}: none.\n")
        return

    print(f"\n{title}: {total} total\n" + "=" * 50)

    for i in range(0, total, page_size):
        page = actions[i : i + page_size]
        start_num = i + 1
        end_num = min(i + page_size, total)

        for offset, line in enumerate(page):
            print(f"{start_num + offset:>4}. {line}")

        remaining = total - end_num
        if remaining <= 0:
            print("=" * 50)
            print(f"End of list ({total} total).\n")
            break

        print("-" * 50)
        user_input = (
            input(
                f"Showing {start_num}-{end_num} of {total}. "
                f"Press Enter for next {min(page_size, remaining)} (or 'q' to stop): "
            )
            .strip()
            .lower()
        )
        if user_input == "q":
            print(
                f"Stopped. {remaining} more item(s) were not shown here — full list is in logs/activity.log\n"
            )
            break
