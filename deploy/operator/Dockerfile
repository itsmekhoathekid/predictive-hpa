FROM golang:1.20 AS builder

ARG TARGETOS=linux
ARG TARGETARCH
WORKDIR /workspace
COPY go.mod go.mod
COPY go.sum go.sum
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=${TARGETOS} GOARCH=${TARGETARCH} go build -a -o manager main.go

FROM python:3.8-slim-buster

WORKDIR /app
COPY algorithms/requirements.txt ./algorithms/requirements.txt
RUN python -m pip install --no-cache-dir -r algorithms/requirements.txt
COPY algorithms/ ./algorithms
# OLS can return an integer plus floating-point noise (for example
# 1.0000000000000002). Prevent ceil() from creating a phantom replica.
RUN sed -i '/^print(math.ceil(model.predict/ c\print(math.ceil(model.predict([[1, 0]])[0] - 1e-9), end="")' \
    algorithms/linear_regression/linear_regression.py && \
    grep -Fq 'model.predict([[1, 0]])[0] - 1e-9' \
    algorithms/linear_regression/linear_regression.py
COPY --from=builder /workspace/manager .
USER 65532:65532
ENTRYPOINT ["/app/manager"]
