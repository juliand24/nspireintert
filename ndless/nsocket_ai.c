/*
 * Ndless/NavNet calculator client for the Python bridge.
 *
 * Build this together with the nsocket library from:
 * https://github.com/compujuckel/nsocket
 *
 * The host side must forward NavNet service 0x8001 to the Python TCP service.
 * This program sends one JSON object per line and prints the JSON response.
 */
#include <stdio.h>
#include <string.h>
#include "nsocket.h"

#define BRIDGE_HOST "192.168.0.2"
#define BRIDGE_PORT 8766

int main(void) {
    char question[512];
    char request[640];
    char response[1600];
    int received;

    if (ns_init() < 0 || ns_connect(BRIDGE_HOST, BRIDGE_PORT) < 0) {
        puts("Could not connect to Python bridge.");
        ns_stop();
        return 1;
    }

    puts("Connected to Python bridge. Enter a question:");
    if (!fgets(question, sizeof(question), stdin)) {
        ns_stop();
        return 1;
    }
    question[strcspn(question, "\r\n")] = '\0';
    snprintf(
        request, sizeof(request),
        "{\"id\":\"nspire-1\",\"question\":\"%s\"}\n", question
    );
    if (ns_send(request, strlen(request)) < 0) {
        puts("Could not send question.");
        ns_stop();
        return 1;
    }

    ns_set_timeout(60000);
    received = ns_recv(response, sizeof(response) - 1);
    if (received <= 0) {
        puts("No response from Python bridge.");
        ns_stop();
        return 1;
    }
    response[received] = '\0';
    puts(response);
    ns_stop();
    return 0;
}
