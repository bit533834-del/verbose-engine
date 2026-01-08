"""
HLTV Parser для CS2
Собирает топ-50 команд и их матчи за 2025-2026

ЗАПУСК: python hltv_parser.py

Требования:
  pip install selenium webdriver-manager

Парсер откроет браузер Chrome и соберёт данные автоматически.
"""

import json
import time
import re
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
except ImportError:
    print("Установи зависимости:")
    print("  pip install selenium webdriver-manager")
    exit(1)


@dataclass
class Team:
    rank: int
    name: str
    team_id: int
    url: str


@dataclass
class Match:
    match_id: int
    url: str
    date: str
    team1: str
    team2: str
    score: str
    event: str


class HLTVParser:
    BASE_URL = "https://www.hltv.org"

    def __init__(self, output_dir: str = "data", headless: bool = False):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.teams: list[Team] = []
        self.matches: dict[str, list[Match]] = {}
        self.headless = headless
        self.driver = None

    def _init_driver(self):
        """Initialize Chrome driver."""
        options = Options()
        if self.headless:
            options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.implicitly_wait(10)

    def _close_driver(self):
        """Close browser."""
        if self.driver:
            self.driver.quit()
            self.driver = None

    def parse_top_teams(self, limit: int = 50) -> list[Team]:
        """Parse top N teams from HLTV ranking."""
        print(f"\n{'='*50}")
        print(f"Загружаю топ {limit} команд с HLTV...")
        print(f"{'='*50}")

        if not self.driver:
            self._init_driver()

        self.driver.get(f"{self.BASE_URL}/ranking/teams")
        time.sleep(3)  # Wait for page load

        teams = []

        try:
            # Find all ranked teams
            team_elements = self.driver.find_elements(By.CSS_SELECTOR, ".ranked-team")

            for i, elem in enumerate(team_elements[:limit], 1):
                try:
                    # Get team link
                    link = elem.find_element(By.CSS_SELECTOR, "a.moreLink")
                    url = link.get_attribute("href")

                    # Extract team ID from URL
                    match = re.search(r'/team/(\d+)/', url)
                    team_id = int(match.group(1)) if match else 0

                    # Get team name
                    name_elem = elem.find_element(By.CSS_SELECTOR, ".name")
                    name = name_elem.text.strip()

                    team = Team(rank=i, name=name, team_id=team_id, url=url)
                    teams.append(team)
                    print(f"  #{i}: {name}")

                except Exception as e:
                    print(f"  Ошибка парсинга команды #{i}: {e}")
                    continue

        except Exception as e:
            print(f"Ошибка: {e}")
            # Fallback: try regex on page source
            html = self.driver.page_source
            pattern = r'href="(/team/(\d+)/([^"]+))"'
            found = re.findall(pattern, html)

            seen = set()
            for url_path, team_id, name in found:
                if team_id in seen or len(teams) >= limit:
                    continue
                seen.add(team_id)

                name = name.replace("-", " ").title()
                team = Team(
                    rank=len(teams) + 1,
                    name=name,
                    team_id=int(team_id),
                    url=f"{self.BASE_URL}{url_path}"
                )
                teams.append(team)
                print(f"  #{team.rank}: {name}")

        self.teams = teams
        self._save_teams()
        return teams

    def parse_team_matches(
        self,
        team: Team,
        start_date: str = "2025-01-01",
        end_date: str = "2026-12-31"
    ) -> list[Match]:
        """Parse all matches for a team within date range."""
        print(f"\n  Загружаю матчи для {team.name}...")

        if not self.driver:
            self._init_driver()

        # HLTV results page for team
        url = f"{self.BASE_URL}/results?team={team.team_id}&startDate={start_date}&endDate={end_date}"
        self.driver.get(url)
        time.sleep(2)

        matches = []
        seen_ids = set()

        try:
            # Find all match links
            match_links = self.driver.find_elements(By.CSS_SELECTOR, "a.a-reset[href*='/matches/']")

            for link in match_links:
                try:
                    href = link.get_attribute("href")
                    match_id_search = re.search(r'/matches/(\d+)/', href)
                    if not match_id_search:
                        continue

                    match_id = match_id_search.group(1)
                    if match_id in seen_ids:
                        continue
                    seen_ids.add(match_id)

                    # Try to get match details from the element
                    parent = link
                    date_str = ""
                    team1, team2 = "", ""
                    score = ""
                    event = ""

                    try:
                        # Get teams
                        teams_elems = parent.find_elements(By.CSS_SELECTOR, ".team")
                        if len(teams_elems) >= 2:
                            team1 = teams_elems[0].text.strip()
                            team2 = teams_elems[1].text.strip()

                        # Get score
                        score_elem = parent.find_elements(By.CSS_SELECTOR, ".result-score")
                        if score_elem:
                            score = score_elem[0].text.strip()
                    except:
                        pass

                    match = Match(
                        match_id=int(match_id),
                        url=href,
                        date=date_str,
                        team1=team1,
                        team2=team2,
                        score=score,
                        event=event
                    )
                    matches.append(match)

                except Exception as e:
                    continue

        except Exception as e:
            print(f"    Ошибка: {e}")
            # Fallback to regex
            html = self.driver.page_source
            pattern = r'href="(/matches/(\d+)/[^"]+)"'
            found = re.findall(pattern, html)

            for url_path, match_id in found:
                if match_id in seen_ids:
                    continue
                seen_ids.add(match_id)

                match = Match(
                    match_id=int(match_id),
                    url=f"{self.BASE_URL}{url_path}",
                    date="",
                    team1="",
                    team2="",
                    score="",
                    event=""
                )
                matches.append(match)

        print(f"    Найдено матчей: {len(matches)}")
        self.matches[team.name] = matches
        return matches

    def parse_all_teams_matches(
        self,
        start_date: str = "2025-01-01",
        end_date: str = "2026-12-31"
    ):
        """Parse matches for all teams."""
        if not self.teams:
            self.parse_top_teams()

        print(f"\n{'='*50}")
        print(f"Собираю матчи для {len(self.teams)} команд")
        print(f"Период: {start_date} - {end_date}")
        print(f"{'='*50}")

        for i, team in enumerate(self.teams, 1):
            print(f"\n[{i}/{len(self.teams)}] {team.name}")
            self.parse_team_matches(team, start_date, end_date)
            self._save_matches()  # Save after each team
            time.sleep(1)  # Rate limiting

    def _save_teams(self):
        """Save teams to JSON."""
        filepath = self.output_dir / "teams_top50.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump([asdict(t) for t in self.teams], f, ensure_ascii=False, indent=2)
        print(f"\n✓ Команды сохранены: {filepath}")

    def _save_matches(self):
        """Save matches to JSON."""
        filepath = self.output_dir / "matches_2025_2026.json"
        data = {
            team: [asdict(m) for m in matches]
            for team, matches in self.matches.items()
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✓ Матчи сохранены: {filepath}")

    def _save_urls_only(self):
        """Save just match URLs to a simple text file."""
        filepath = self.output_dir / "match_urls.txt"
        urls = set()
        for matches in self.matches.values():
            for m in matches:
                urls.add(m.url)

        with open(filepath, "w", encoding="utf-8") as f:
            for url in sorted(urls):
                f.write(url + "\n")
        print(f"✓ URLs сохранены: {filepath} ({len(urls)} уникальных)")

    def get_all_match_urls(self) -> list[str]:
        """Get flat list of all match URLs."""
        urls = []
        for matches in self.matches.values():
            urls.extend([m.url for m in matches])
        return list(set(urls))

    def run(self):
        """Main entry point."""
        try:
            self.parse_top_teams(limit=50)
            self.parse_all_teams_matches(
                start_date="2025-01-01",
                end_date="2026-12-31"
            )
            self._save_urls_only()

            # Summary
            all_urls = self.get_all_match_urls()
            print(f"\n{'='*50}")
            print(f"ГОТОВО!")
            print(f"{'='*50}")
            print(f"Команд: {len(self.teams)}")
            print(f"Уникальных матчей: {len(all_urls)}")
            print(f"\nФайлы:")
            print(f"  - {self.output_dir}/teams_top50.json")
            print(f"  - {self.output_dir}/matches_2025_2026.json")
            print(f"  - {self.output_dir}/match_urls.txt")

        finally:
            self._close_driver()


def main():
    parser = HLTVParser(output_dir="data", headless=False)
    parser.run()


if __name__ == "__main__":
    main()
