"""Offline tests for external GitHub Pages 404 and broken-data detection."""
import json
import unittest
from urllib.error import HTTPError
from cloud.public_site_health import check, retry

SITE = "https://andys3-design.github.io/MLB-Postseason-Forecast-Model/"


def make_fetch(base=SITE):
    data={"predictions":[{"game_id":"849811"}],
          "updated_utc":"2026-10-14T22:36:51Z",
          "full_distribution_validation":{"settled_distribution_complete_games":1}}
    payload={base:b"<!DOCTYPE html><title>MLB Forecast Lab</title>",
             base+"data.json":json.dumps(data).encode()}
    def inner(url):
        if url not in payload:
            raise AssertionError("Wrong public site path "+url)
        return payload[url]
    return inner


class PagesHealthTests(unittest.TestCase):
    def test_actual_site_and_data_urls_not_root(self):
        result=check(SITE,fetcher=make_fetch())
        self.assertEqual(result["status"],"reachable")
        self.assertEqual(result["forecasts"],1)
        self.assertTrue(result["data_url"].endswith(
            "/MLB-Postseason-Forecast-Model/data.json"))

    def test_public_404_is_not_counted_as_success(self):
        def not_found(url):
            raise HTTPError(url,404,"There isn't a GitHub Pages site here",{},None)
        with self.assertRaisesRegex(RuntimeError,"still inaccessible"):
            retry(SITE,attempts=3,delay_seconds=0,
                  checker=lambda url:check(url,fetcher=not_found),
                  sleeper=lambda delay:None)

    def test_page_appears_after_cdn_propagation(self):
        calls=[]
        def delayed(url):
            calls.append(url)
            if len(calls)==1:
                raise HTTPError(url,404,"not ready",{},None)
            return check(url,fetcher=make_fetch())
        result=retry(SITE,attempts=3,delay_seconds=0,checker=delayed,
                     sleeper=lambda delay:None)
        self.assertEqual(result["attempt"],2)

    def test_invalid_json_and_wrong_published_site_rejected(self):
        with self.assertRaises(ValueError):
            check("http://andys3-design.github.io/MLB-Postseason-Forecast-Model/",
                  fetcher=make_fetch())
        with self.assertRaisesRegex(ValueError,"not the MLB Forecast Lab"):
            check(SITE,fetcher=lambda _:b"<html>Wrong page</html>")
        good=make_fetch()
        with self.assertRaises(json.JSONDecodeError):
            check(SITE,fetcher=lambda u:good(u) if u==SITE else b"{unparseable")

    def test_missing_v17_report_is_not_deployed_version(self):
        data=b'{"predictions":[],"updated_utc":"2026-10-14T22:30:00Z"}'
        with self.assertRaisesRegex(ValueError,"V17 distribution validation"):
            check(SITE,fetcher=lambda u:
                b"<html>MLB Forecast Lab</html>" if u==SITE else data)


if __name__=="__main__":
    unittest.main()
