# Built only by ci_seed_mirror.yml (infrequent). E2E pulls the GHCR pin.
FROM docker.io/library/golang:1.22-alpine AS build
WORKDIR /src
COPY main.go .
RUN CGO_ENABLED=0 go build -o /http-echo main.go
FROM docker.io/library/alpine:3.20
COPY --from=build /http-echo /http-echo
ENTRYPOINT ["/http-echo"]
