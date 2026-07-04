import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  stages: [
    { duration: "15s", target: 5 },
    { duration: "30s", target: 10 },
    { duration: "15s", target: 0 },
  ],

  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<700"],
  },
};

const API_URL =
  "https://szcf8ifdpe.execute-api.us-east-1.amazonaws.com";

const JOB_ID =
  "3c758cc7-6040-4645-8898-ca160125d5e5";

export default function () {
  const healthResponse = http.get(`${API_URL}/health`);

  check(healthResponse, {
    "health returns 200": (response) => response.status === 200,
  });

  const jobResponse = http.get(`${API_URL}/jobs/${JOB_ID}`);

  check(jobResponse, {
    "job returns 200": (response) => response.status === 200,
  });

  const reportResponse = http.get(
    `${API_URL}/reports/${JOB_ID}`
  );

  check(reportResponse, {
    "report returns 200": (response) => response.status === 200,
  });

  sleep(1);
}
