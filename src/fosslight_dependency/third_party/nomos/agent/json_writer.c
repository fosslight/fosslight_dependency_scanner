/***************************************************************
 Copyright (C) 2019 Siemens AG
 Author: Gaurav Mishra <mishra.gaurav@siemens.com>

 This program is free software; you can redistribute it and/or
 modify it under the terms of the GNU General Public License
 version 2 as published by the Free Software Foundation.

 This program is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License along
 with this program; if not, write to the Free Software Foundation, Inc.,
 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

 ***************************************************************/

#include "json_writer.h"
#include "nomos.h"
#include "nomos_utils.h"
#include <json-c/json.h>

void writeJson()
{
  char realPathOfTarget[PATH_MAX];
  json_object *result = json_object_new_object();
  json_object *licenses = json_object_new_array();
  json_object *fileLocation = NULL;
  json_object *aLicense = NULL;
  size_t i = 0;

  parseLicenseList();
  while (cur.licenseList[i] != NULL)
  {
    aLicense = json_object_new_string(cur.licenseList[i]);
    cur.licenseList[i] = NULL;
    json_object_array_add(licenses, aLicense);
    ++i;
  }
  if (optionIsSet(OPTS_LONG_CMD_OUTPUT)
      && realpath(cur.targetFile, realPathOfTarget))
  {
    fileLocation = json_object_new_string(realPathOfTarget);
  }
  else
  {
    fileLocation = json_object_new_string(basename(cur.targetFile));
  }
  json_object_object_add(result, "file", fileLocation);
  json_object_object_add(result, "licenses", licenses);
  char *prettyJson = unescapePathSeparator(
    json_object_to_json_string_ext(result, JSON_C_TO_STRING_PRETTY));
  sem_wait(mutexJson);
  if (*printcomma)
  {
    printf(",%s\n", prettyJson);
  }
  else
  {
    *printcomma = true;
    printf("%s\n", prettyJson);
  }
  fflush(stdout);
  sem_post(mutexJson);
  free(prettyJson);
  json_object_put(result);
}

char *unescapePathSeparator(const char* json)
{
  const char *escapedSeparator = "\\/";
  const char *pathSeparator = "/";
  const int escPathLen = 2;
  const int pathSepLen = 1;
  size_t resultLength = 0;
  size_t remainingLength = -1;
  char *result;
  char *tmp;
  char *tempjson;
  int count;
  char *strtok_str;
  if (!json)
  {
    return NULL;
  }
  tempjson = strdup(json);

  tmp = tempjson;
  for (count = 0; (tmp = strstr(tmp, escapedSeparator)); count++)
  {
    tmp += escPathLen;
  }

  resultLength = strlen(tempjson) - ((escPathLen - pathSepLen) * count);

  strtok_str = strtok(tempjson, escapedSeparator);
  if (strtok_str == NULL)
  {
    return NULL;
  }
  result = (char*) calloc(resultLength + 1, sizeof(char));

  strncpy(result, strtok_str, resultLength);
  remainingLength = resultLength - strlen(result);

  while (count-- && remainingLength > 0)
  {
    strncat(result, pathSeparator, remainingLength);
    strncat(result, strtok(NULL, escapedSeparator), remainingLength - 1);
    remainingLength = resultLength - strlen(result);
  }
  free(tempjson);
  return result;
}

inline void initializeJson()
{
  mutexJson = (sem_t *) mmap(NULL, sizeof(sem_t),
    PROT_READ | PROT_WRITE, MAP_ANONYMOUS | MAP_SHARED, -1, 0);
  printcomma = (gboolean *) mmap(NULL, sizeof(gboolean),
    PROT_READ | PROT_WRITE, MAP_SHARED | MAP_ANONYMOUS, -1, 0);
  sem_init(mutexJson, 2, SEM_DEFAULT_VALUE);
}

inline void destroyJson()
{
  sem_destroy(mutexJson);
  munmap(printcomma, sizeof(gboolean));
  munmap(mutexJson, sizeof(sem_t));
}
