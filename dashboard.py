"""Serve a browser dashboard for Poker Flat auroral imagery and GOES Hp."""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urljoin, urlparse
from urllib.request import Request, urlopen


IMAGE_DIRECTORY_URL = "https://allsky.gi.alaska.edu/PKR/tagged_cam/"
GOES_BASE_URL = "https://services.swpc.noaa.gov/json/goes/primary/"
GOES_RANGE_TO_FILE = {
		"6-hour": "magnetometers-6-hour.json",
		"1-day": "magnetometers-1-day.json",
		"3-day": "magnetometers-3-day.json",
		"7-day": "magnetometers-7-day.json",
}
DEFAULT_GOES_RANGE = "6-hour"
IMAGE_PATTERN = re.compile(r"PKR_(\d{12})\.jpg", re.IGNORECASE)
REQUEST_TIMEOUT_SECONDS = 20
USER_AGENT = "aurora-scripts-dashboard/0.1"


HTML_PAGE = """<!doctype html>
<html lang="en">
	<head>
		<meta charset="utf-8">
		<meta name="viewport" content="width=device-width, initial-scale=1">
		<title>Poker Flat Aurora Dashboard</title>
		<style>
			:root {
				--bg: #081218;
				--panel: #10212b;
				--panel-border: #2a4857;
				--accent: #8ee38a;
				--accent-2: #7cc4ff;
				--text: #ecf6f2;
				--muted: #9eb9bd;
				--danger: #ff8f70;
			}

			* {
				box-sizing: border-box;
			}

			body {
				margin: 0;
				height: 100dvh;
				overflow: hidden;
				font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
				color: var(--text);
				background:
					radial-gradient(circle at top, rgba(74, 143, 107, 0.22), transparent 30%),
					linear-gradient(180deg, #040b0f 0%, var(--bg) 45%, #06161d 100%);
			}

			main {
				width: min(1400px, calc(100vw - 20px));
				height: 100dvh;
				margin: 0 auto;
				padding: 8px 0 10px;
				display: grid;
				grid-template-rows: auto 1fr;
				gap: 8px;
			}

			.header {
				display: flex;
				justify-content: space-between;
				gap: 16px;
				align-items: baseline;
				padding: 0 4px;
			}

			.header-status {
				display: flex;
				flex-direction: column;
				align-items: flex-end;
				gap: 4px;
			}

			.title {
				margin: 0;
				font-size: clamp(1.5rem, 2vw + 1rem, 2.6rem);
				font-weight: 650;
				letter-spacing: 0.02em;
			}

			.subtitle,
			.status-line {
				color: var(--muted);
				font-size: 0.95rem;
			}

			.grid {
				display: grid;
				height: 100%;
				min-height: 0;
				grid-template-rows: minmax(0, 1.5fr) minmax(0, 1fr);
				gap: 8px;
			}

			.panel {
				background: linear-gradient(180deg, rgba(16, 33, 43, 0.96), rgba(8, 18, 24, 0.94));
				border: 1px solid rgba(42, 72, 87, 0.9);
				border-radius: 18px;
				overflow: hidden;
				box-shadow: 0 20px 50px rgba(0, 0, 0, 0.25);
				min-height: 0;
			}

			.image-panel {
				display: flex;
				min-height: 0;
			}

			.image-wrap {
				position: relative;
				width: 100%;
				height: 100%;
				min-height: 0;
			}

			.image-figure {
				position: relative;
				width: 100%;
				height: 100%;
				min-width: 0;
				min-height: 0;
			}

			#aurora-image {
				width: 100%;
				height: 100%;
				object-fit: contain;
				object-position: center center;
				background: #030608;
				display: block;
			}

			.stale-banner {
				position: absolute;
				inset: 16px auto auto 16px;
				padding: 14px 18px;
				border: 2px solid rgba(255, 143, 112, 0.8);
				border-radius: 14px;
				background: rgba(71, 24, 14, 0.72);
				color: #fff3ef;
				font-size: clamp(1.15rem, 1.6vw + 0.7rem, 2rem);
				font-weight: 700;
				letter-spacing: 0.04em;
				text-transform: uppercase;
				display: none;
				backdrop-filter: blur(6px);
			}

			.plot-panel {
				display: grid;
				grid-template-rows: auto 1fr;
			}

			.plot-header {
				display: flex;
				justify-content: space-between;
				gap: 12px;
				padding: 10px 14px 0;
			}

			.goes-controls {
				display: flex;
				align-items: center;
				gap: 8px;
			}

			.goes-controls label {
				font-size: 0.88rem;
				color: var(--muted);
			}

			.goes-select {
				background: rgba(8, 18, 24, 0.9);
				border: 1px solid rgba(42, 72, 87, 0.9);
				border-radius: 8px;
				color: var(--text);
				font: inherit;
				padding: 6px 8px;
			}

			.plot-title {
				margin: 0;
				font-size: 1.05rem;
				font-weight: 650;
			}

			.plot-body {
				min-height: 0;
				padding: 6px 12px 10px;
			}

			#goes-plot {
				width: 100%;
				height: 100%;
				display: block;
			}

			.error {
				color: var(--danger);
			}

			@media (max-width: 900px) {
				main {
					width: min(100vw - 10px, 1400px);
					padding: 6px 0 8px;
					gap: 6px;
				}

				.header,
				.plot-header {
					flex-direction: column;
				}

				.header-status {
					align-items: flex-start;
				}

				.grid {
					grid-template-rows: minmax(0, 1.15fr) minmax(0, 1fr);
					gap: 6px;
				}

				.plot-header {
					padding: 8px 10px 0;
					gap: 8px;
				}

				.plot-body {
					padding: 6px 8px 8px;
				}

				.stale-banner {
					inset: 10px auto auto 10px;
					font-size: clamp(1rem, 1.5vw + 0.6rem, 1.35rem);
					padding: 10px 12px;
				}
			}
		</style>
	</head>
	<body>
		<main>
			<div class="header">
				<div>
					<h1 class="title">Mike's Aurora Dashboard</h1>
				</div>
				<div class="header-status">
					<div class="status-line" id="refresh-status">Loading...</div>
				</div>
			</div>

			<div class="grid">
				<section class="panel image-panel">
					<div class="image-wrap">
						<div class="image-figure">
							<img id="aurora-image" alt="Latest auroral image">
							<div class="stale-banner" id="stale-banner">Stale image</div>
						</div>
					</div>
				</section>

				<section class="panel plot-panel">
					<div class="plot-header">
						<div>
							<h2 class="plot-title" id="goes-title">GOES-19 6-hour Magnetometer, Hp component</h2>
						</div>
						<div class="goes-controls">
							<label for="goes-range">Time Range</label>
							<select id="goes-range" class="goes-select">
								<option value="6-hour" selected>6-hour</option>
								<option value="1-day">1-day</option>
								<option value="3-day">3-day</option>
								<option value="7-day">7-day</option>
							</select>
							<label for="min-y-select">Min Y</label>
							<select id="min-y-select" class="goes-select">
								<option value="auto" selected>auto</option>
								<option value="0">0</option>
							</select>
						</div>
					</div>
					<div class="plot-body">
						<canvas id="goes-plot"></canvas>
					</div>
				</section>
			</div>
		</main>

		<script>
			const refreshStatus = document.getElementById('refresh-status');
			const auroraImage = document.getElementById('aurora-image');
			const staleBanner = document.getElementById('stale-banner');
			const goesRange = document.getElementById('goes-range');
			const minYSelect = document.getElementById('min-y-select');
			const goesTitle = document.getElementById('goes-title');
			const canvas = document.getElementById('goes-plot');
			const context = canvas.getContext('2d');

			let lastPayload = null;

			function formatUtc(isoString) {
				const date = new Date(isoString);
				return new Intl.DateTimeFormat('en-US', {
					year: 'numeric',
					month: 'short',
					day: '2-digit',
					hour: '2-digit',
					minute: '2-digit',
					second: '2-digit',
					timeZone: 'UTC',
					hour12: false,
				}).format(date) + ' UTC';
			}

			function resizeCanvas() {
				const dpr = window.devicePixelRatio || 1;
				const rect = canvas.getBoundingClientRect();
				const width = Math.max(1, Math.floor(rect.width * dpr));
				const height = Math.max(1, Math.floor(rect.height * dpr));
				if (canvas.width !== width || canvas.height !== height) {
					canvas.width = width;
					canvas.height = height;
				}
				context.setTransform(1, 0, 0, 1, 0, 0);
				context.scale(dpr, dpr);
			}

			function drawPlot(times, values) {
				resizeCanvas();

				const width = canvas.clientWidth;
				const height = canvas.clientHeight;
				context.clearRect(0, 0, width, height);

				if (!values.length) {
					context.fillStyle = '#ff8f70';
					context.font = '16px IBM Plex Sans, sans-serif';
					context.fillText('No GOES data available', 16, 28);
					return;
				}

				const margin = { top: 14, right: 18, bottom: 34, left: 60 };
				const plotWidth = width - margin.left - margin.right;
				const plotHeight = height - margin.top - margin.bottom;

				const minY = Math.min(...values);
				const maxY = Math.max(...values);
				const yPadding = Math.max(2, maxY * 0.08);
				const yPaddingDown = Math.max(2, (maxY - minY) * 0.1);
				const y0 = minYSelect.value === '0' ? 0 : minY - yPaddingDown;
				const y1 = maxY + yPadding;

				const x = (index) => margin.left + (index / Math.max(values.length - 1, 1)) * plotWidth;
				const y = (value) => margin.top + ((y1 - value) / Math.max(y1 - y0, 1e-6)) * plotHeight;

				context.strokeStyle = 'rgba(124, 196, 255, 0.18)';
				context.lineWidth = 1;
				for (let i = 0; i <= 4; i += 1) {
					const yy = margin.top + (plotHeight * i) / 4;
					context.beginPath();
					context.moveTo(margin.left, yy);
					context.lineTo(width - margin.right, yy);
					context.stroke();
				}

				context.strokeStyle = 'rgba(236, 246, 242, 0.35)';
				context.beginPath();
				context.moveTo(margin.left, margin.top);
				context.lineTo(margin.left, height - margin.bottom);
				context.lineTo(width - margin.right, height - margin.bottom);
				context.stroke();

				context.font = '12px IBM Plex Sans, sans-serif';
				context.fillStyle = '#9eb9bd';
				context.textAlign = 'right';
				context.textBaseline = 'middle';
				for (let i = 0; i <= 4; i += 1) {
					const value = y1 - ((y1 - y0) * i) / 4;
					const yy = margin.top + (plotHeight * i) / 4;
					context.fillText(value.toFixed(1), margin.left - 10, yy);
				}

				context.save();
				context.translate(12, margin.top + plotHeight / 2);
				context.rotate(-Math.PI / 2);
				context.textAlign = 'center';
				context.textBaseline = 'middle';
				context.fillText('Hp [nT]', 0, 0);
				context.restore();

				context.textAlign = 'center';
				context.textBaseline = 'top';
				const tickCount = Math.min(6, times.length);
				for (let i = 0; i < tickCount; i += 1) {
					const index = Math.round((i / Math.max(tickCount - 1, 1)) * (times.length - 1));
					const date = new Date(times[index]);
					const label = `${String(date.getUTCHours()).padStart(2, '0')}:${String(date.getUTCMinutes()).padStart(2, '0')}`;
					context.fillText(label, x(index), height - margin.bottom + 8);
				}

				const quietColor = 'rgba(124, 196, 255, 0.9)';
				const moderateChangeColor = 'rgba(142, 227, 138, 0.95)';
				const strongChangeColor = 'rgba(255, 165, 102, 0.95)';

				const segmentColor = (delta) => {
					if (delta > 5) {
						return strongChangeColor;
					}
					if (delta >= 1) {
						return moderateChangeColor;
					}
					return quietColor;
				};

				context.lineWidth = 2.5;
				for (let i = 1; i < values.length; i += 1) {
					const x0 = x(i - 1);
					const y0p = y(values[i - 1]);
					const x1 = x(i);
					const y1p = y(values[i]);
					const delta = Math.abs(values[i] - values[i - 1]);

					context.strokeStyle = segmentColor(delta);
					context.beginPath();
					context.moveTo(x0, y0p);
					context.lineTo(x1, y1p);
					context.stroke();
				}

			}

			function applyPayload(payload) {
				lastPayload = payload;

				const imageState = payload.image.is_stale ? 'Stale image' : 'Up-to-date';
				refreshStatus.textContent = `Last refresh: ${formatUtc(payload.server_time_utc)} (${imageState})`;
				const goesSatellite = payload.goes.satellite ?? '--';
				goesTitle.textContent = `GOES-${goesSatellite} ${payload.goes.range} Magnetometer, Hp component`;
				auroraImage.src = `${payload.image.url}?t=${Date.now()}`;

				if (payload.image.is_stale) {
					staleBanner.style.display = 'block';
					staleBanner.textContent = 'Stale image';
				} else {
					staleBanner.style.display = 'none';
					staleBanner.textContent = '';
				}

				const points = payload.goes.points;
				drawPlot(points.map((point) => point.time_utc), points.map((point) => point.hp));
			}

			async function refreshDashboard() {
				try {
					const selectedRange = goesRange.value;
					const response = await fetch(`/api/dashboard?goes_range=${encodeURIComponent(selectedRange)}`, { cache: 'no-store' });
					if (!response.ok) {
						throw new Error(`HTTP ${response.status}`);
					}
					const payload = await response.json();
					applyPayload(payload);
				} catch (error) {
					refreshStatus.innerHTML = `<span class="error">Refresh failed: ${error.message}</span>`;
					if (lastPayload) {
						applyPayload(lastPayload);
					}
				}
			}

			window.addEventListener('resize', () => {
				if (lastPayload) {
					const points = lastPayload.goes.points;
					drawPlot(points.map((point) => point.time_utc), points.map((point) => point.hp));
				}
			});

			goesRange.addEventListener('change', () => {
				refreshDashboard();
			});

			minYSelect.addEventListener('change', () => {
				if (lastPayload) {
					const points = lastPayload.goes.points;
					drawPlot(points.map((point) => point.time_utc), points.map((point) => point.hp));
				}
			});

			refreshDashboard();
			setInterval(refreshDashboard, 60_000);
		</script>
	</body>
</html>
"""


def fetch_text(url: str) -> str:
		request = Request(url, headers={"User-Agent": USER_AGENT})
		with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
				return response.read().decode("utf-8")


def fetch_json(url: str) -> Any:
		request = Request(url, headers={"User-Agent": USER_AGENT})
		with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
				return json.loads(response.read().decode("utf-8"))


def parse_image_timestamp(filename: str) -> datetime:
		match = IMAGE_PATTERN.search(filename)
		if match is None:
				raise ValueError(f"Could not parse timestamp from {filename!r}")
		return datetime.strptime(match.group(1), "%y%m%d%H%M%S").replace(tzinfo=UTC)


def fetch_latest_image() -> dict[str, Any]:
		directory_listing = fetch_text(IMAGE_DIRECTORY_URL)
		filenames = sorted(set(IMAGE_PATTERN.findall(directory_listing)))
		if not filenames:
				raise ValueError("No image filenames found in Poker Flat directory listing")

		latest_stem = max(filenames)
		filename = f"PKR_{latest_stem}.jpg"
		timestamp = parse_image_timestamp(filename)
		now = datetime.now(UTC)
		age_seconds = max(0.0, (now - timestamp).total_seconds())
		return {
				"filename": filename,
				"timestamp_utc": timestamp.isoformat().replace("+00:00", "Z"),
				"url": urljoin(IMAGE_DIRECTORY_URL, filename),
				"age_seconds": age_seconds,
				"is_stale": age_seconds > 60,
		}


def fetch_goes_hp(goes_range: str) -> dict[str, Any]:
		if goes_range not in GOES_RANGE_TO_FILE:
			raise ValueError(f"Unsupported GOES range: {goes_range}")

		goes_url = urljoin(GOES_BASE_URL, GOES_RANGE_TO_FILE[goes_range])
		rows = fetch_json(goes_url)
		points: list[dict[str, Any]] = []
		satellite: int | None = None
		for row in rows:
				time_utc = row.get("time_tag")
				hp = row.get("Hp")
				if satellite is None:
					sat_value = row.get("satellite")
					if isinstance(sat_value, int):
						satellite = sat_value
				if time_utc is None or hp is None:
						continue
				try:
						points.append({"time_utc": time_utc, "hp": float(hp)})
				except (TypeError, ValueError):
						continue

		if not points:
				raise ValueError("No valid Hp values found in GOES feed")

		return {"points": points, "range": goes_range, "satellite": satellite}


def build_dashboard_payload(goes_range: str) -> bytes:
		payload = {
				"server_time_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
				"image": fetch_latest_image(),
				"goes": fetch_goes_hp(goes_range),
		}
		return json.dumps(payload).encode("utf-8")


class DashboardHandler(BaseHTTPRequestHandler):
		def do_GET(self) -> None:
				parsed_url = urlparse(self.path)

				if parsed_url.path in {"/", "/index.html"}:
						self.send_response(HTTPStatus.OK)
						self.send_header("Content-Type", "text/html; charset=utf-8")
						self.end_headers()
						self.wfile.write(HTML_PAGE.encode("utf-8"))
						return

				if parsed_url.path == "/api/dashboard":
						query = parse_qs(parsed_url.query)
						goes_range = query.get("goes_range", [DEFAULT_GOES_RANGE])[0]
						try:
								body = build_dashboard_payload(goes_range)
						except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as error:
								self.send_response(HTTPStatus.BAD_GATEWAY)
								self.send_header("Content-Type", "application/json; charset=utf-8")
								self.end_headers()
								self.wfile.write(json.dumps({"error": str(error)}).encode("utf-8"))
								return

						self.send_response(HTTPStatus.OK)
						self.send_header("Content-Type", "application/json; charset=utf-8")
						self.send_header("Cache-Control", "no-store")
						self.end_headers()
						self.wfile.write(body)
						return

				self.send_response(HTTPStatus.NOT_FOUND)
				self.end_headers()

		def log_message(self, format: str, *args: Any) -> None:
				return


def parse_args() -> argparse.Namespace:
		parser = argparse.ArgumentParser(description=__doc__)
		parser.add_argument("--host", default="127.0.0.1", help="Interface to bind")
		parser.add_argument("--port", type=int, default=8000, help="Port to serve on")
		return parser.parse_args()


def main() -> None:
		args = parse_args()
		server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
		print(f"Serving dashboard at http://{args.host}:{args.port}")
		try:
				server.serve_forever()
		except KeyboardInterrupt:
				pass
		finally:
				server.server_close()


if __name__ == "__main__":
		main()

