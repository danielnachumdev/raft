package main

import (
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"
)

func main() {
	listen := flag.String("listen", ":5678", "")
	text := flag.String("text", "hello-world", "")
	flag.Parse()
	log.SetOutput(os.Stdout)
	log.SetFlags(0)
	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		log.Printf("echo %s %s", r.Method, r.URL.Path)
		fmt.Fprint(w, *text)
	})
	log.Printf("Listening on %s", *listen)
	_ = http.ListenAndServe(*listen, nil)
}
